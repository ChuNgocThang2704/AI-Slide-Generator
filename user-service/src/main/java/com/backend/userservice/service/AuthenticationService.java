package com.backend.userservice.service;

import com.backend.userservice.constant.RoleEnum;
import com.backend.userservice.constant.Status;
import com.backend.userservice.dto.request.*;
import com.backend.userservice.dto.response.*;
import com.backend.userservice.entity.RoleEntity;
import com.backend.userservice.entity.UserEntity;
import com.backend.userservice.entity.UserProfileEntity;
import com.backend.userservice.exception.AppException;
import com.backend.userservice.exception.ErrorCode;
import com.backend.userservice.repository.RoleRepository;
import com.backend.userservice.repository.UserRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.nimbusds.jose.JOSEException;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.JWSObject;
import com.nimbusds.jose.JWSVerifier;
import com.nimbusds.jose.Payload;
import com.nimbusds.jose.crypto.MACSigner;
import com.nimbusds.jose.crypto.MACVerifier;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import java.text.ParseException;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.*;
import java.util.concurrent.TimeUnit;
import lombok.RequiredArgsConstructor;
import lombok.experimental.NonFinal;
import lombok.extern.slf4j.Slf4j;
import org.apache.coyote.BadRequestException;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.http.MediaType;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.util.CollectionUtils;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.web.reactive.function.client.WebClient;

@Service
@RequiredArgsConstructor
@Slf4j
public class AuthenticationService {
    private static final String TOKEN_BLACKLIST_PREFIX = "TOKEN_BLACK_LIST_";
    private static final String ACCESS_TOKEN_TYPE = "access";
    private static final String REFRESH_TOKEN_TYPE = "refresh";

    private final UserRepository userRepository;
    private final RabbitTemplate rabbitTemplate;
    private final ObjectMapper objectMapper;
    private final RoleRepository roleRepository;
    private final RedisTemplate<String, Object> redisTemplate;
    private final PasswordEncoder passwordEncoder;
    private final WebClient webClient = WebClient.builder().build();

    @NonFinal
    @Value("${jwt.signerKey}")
    protected String SIGNER_KEY;

    @NonFinal
    @Value("${jwt.valid-duration}")
    protected long VALID_DURATION;

    @NonFinal
    @Value("${jwt.refreshable-duration}")
    protected long REFRESHABLE_DURATION;

    @NonFinal
    @Value("${google.client-id}")
    protected String googleClientId;

    @NonFinal
    @Value("${google.client-secret}")
    protected String googleClientSecret;

    @NonFinal
    @Value("${google.redirect-uri}")
    protected String googleRedirectUri;

    @NonFinal
    @Value("${google.user-info-uri}")
    protected String googleUserInfoUri;

    @NonFinal
    @Value("${google.token-uri}")
    protected String googleTokenUri;

    @Value("${app.rabbitmq.queue:notification_queue}")
    private String notificationQueue;

    public String register(CreateUserRequest createUserRequest) {
        log.info("[user-service] đăng ký tài khoản mới với email: {}", createUserRequest.getEmail());
        String email = createUserRequest.getEmail() != null ? createUserRequest.getEmail().trim().toLowerCase() : null;
        if (email == null || email.isBlank()) {
            throw new AppException(ErrorCode.EMAIL_IS_REQUIRED);
        }
        if (userRepository.existsByEmail(email)) {
            throw new AppException(ErrorCode.USER_EXISTED);
        }

        UserEntity userEntity = UserEntity.builder()
                .email(email)
                .username(generateUsernameFromEmail(email))
                .build();

        userEntity.setPassword(passwordEncoder.encode(createUserRequest.getPassword()));

        HashSet<RoleEntity> roles = new HashSet<>();
        RoleEntity defaultRole = roleRepository.findById(String.valueOf(RoleEnum.USER_FREE))
                .orElseThrow(() -> new AppException(ErrorCode.ROLE_NOT_FOUND));
        roles.add(defaultRole);
        userEntity.setRoles(roles);
        userEntity.setEmailVerified(false);
        userEntity.setStatus(Status.USER_STATUS.CREATED);

        try {
            userRepository.save(userEntity);
            log.info("[user-service] lưu user thành công, gửi email xác nhận tới: {}", email);
            sendVerificationEmail(userEntity);
        } catch (DataIntegrityViolationException e) {
            throw new AppException(ErrorCode.USER_EXISTED);
        }

        return "Create user successfully";
    }

    private void sendVerificationEmail(UserEntity userEntity) {
        String verificationCode = String.format("%08d", new java.util.Random().nextInt(100000000));
        String redisKey = "VERIFY_ACCOUNT_" + userEntity.getId() + "_" + verificationCode;
        redisTemplate.opsForValue().set(redisKey, "", 15, TimeUnit.MINUTES);

        Map<String, Object> payload = new HashMap<>();
        payload.put("email", userEntity.getEmail());
        payload.put("code", verificationCode);

        EmailRequest emailRequest = EmailRequest.builder()
                .to(userEntity.getEmail())
                .type("REGISTRATION_VERIFY")
                .payload(payload)
                .build();

        try {
            rabbitTemplate.convertAndSend(notificationQueue, emailRequest);
            log.info("Đã đẩy yêu cầu gửi mail xác nhận cho {} vào hàng đợi", userEntity.getEmail());
        } catch (Exception e) {
            log.error("Lỗi khi đẩy message vào RabbitMQ: ", e);
        }
    }

    private SignedJWT verifyToken(String token, boolean isRefresh) throws JOSEException, ParseException {
        JWSVerifier jwsVerifier = new MACVerifier(SIGNER_KEY.getBytes());
        SignedJWT signedJWT = SignedJWT.parse(token);

        boolean verified = signedJWT.verify(jwsVerifier);
        String tokenType = signedJWT.getJWTClaimsSet().getStringClaim("token_type");
        String expectedTokenType = isRefresh ? REFRESH_TOKEN_TYPE : ACCESS_TOKEN_TYPE;
        Date expiryTime = signedJWT.getJWTClaimsSet().getExpirationTime();

        if (!verified || expiryTime.before(new Date()) || !expectedTokenType.equals(tokenType)) {
            throw new AppException(ErrorCode.UNAUTHENTICATED);
        }

        String jwtId = signedJWT.getJWTClaimsSet().getJWTID();
        String userId = signedJWT.getJWTClaimsSet().getSubject();
        if (Boolean.TRUE.equals(redisTemplate.hasKey(TOKEN_BLACKLIST_PREFIX + userId + "_" + jwtId))) {
            throw new AppException(ErrorCode.UNAUTHENTICATED);
        }

        return signedJWT;
    }

    public SignedJWT verifyAccessToken(String token) {
        try {
            return verifyToken(token, false);
        } catch (JOSEException | ParseException e) {
            throw new AppException(ErrorCode.UNAUTHENTICATED);
        }
    }

    private String buildScope(UserEntity user) {
        StringJoiner stringJoiner = new StringJoiner(" ");

        if (!CollectionUtils.isEmpty(user.getRoles())) {
            user.getRoles().forEach(role -> {
                stringJoiner.add("ROLE_" + role.getName());
            });
        }

        return stringJoiner.toString();
    }

    private String generateAccessToken(UserEntity userEntity) {
        return generateToken(userEntity, VALID_DURATION, ACCESS_TOKEN_TYPE);
    }

    private String generateRefreshToken(UserEntity userEntity) {
        return generateToken(userEntity, REFRESHABLE_DURATION, REFRESH_TOKEN_TYPE);
    }

    private String generateToken(UserEntity userEntity, long durationInSeconds, String tokenType) {
        JWSHeader jwsHeader = new JWSHeader(JWSAlgorithm.HS512);

        JWTClaimsSet jwtClaimsSet = new JWTClaimsSet.Builder()
                .subject(userEntity.getId().toString())
                .issuer("ai-slide-generator")
                .issueTime(new Date())
                .expirationTime(new Date(Instant.now().plus(durationInSeconds, ChronoUnit.SECONDS).toEpochMilli()))
                .jwtID(UUID.randomUUID().toString())
                .claim("email", userEntity.getEmail())
                .claim("token_type", tokenType)
                .claim("scope", buildScope(userEntity))
                .build();
        Payload payload = new Payload(jwtClaimsSet.toJSONObject());

        JWSObject jwsObject = new JWSObject(jwsHeader, payload);

        try {
            jwsObject.sign(new MACSigner(SIGNER_KEY.getBytes()));
            return jwsObject.serialize();
        } catch (JOSEException e) {
            log.error("Generate token failed!", e);
            throw new RuntimeException(e);
        }
    }

    public GoogleAuthUrlResponse getGoogleAuthUrl() {
        String authUrl = "https://accounts.google.com/o/oauth2/v2/auth?"
                + "client_id=" + googleClientId
                + "&redirect_uri=" + googleRedirectUri
                + "&response_type=code"
                + "&scope=profile%20email"
                + "&access_type=offline"
                + "&prompt=consent";

        return GoogleAuthUrlResponse.builder()
                .url(authUrl)
                .build();
    }

    public AuthenticationResponse authenticate(AuthenticationRequest request) {
        log.info("[user-service] đăng nhập với email: {}", request.getEmail());
        UserEntity userEntity = userRepository
                .findByEmail(request.getEmail())
                .orElseThrow(() -> new AppException(ErrorCode.USER_NOT_EXISTED));

        boolean authenticated = passwordEncoder.matches(request.getPassword(), userEntity.getPassword());
        if (!authenticated) {
            throw new AppException(ErrorCode.USERNAME_OR_PASSWORD_INCORRECT);
        }

        if (!userEntity.isEmailVerified()){
            throw new AppException(ErrorCode.USER_IS_NOT_ACTIVE);
        }

        userEntity.setLastLoginAt(Instant.now());
        userEntity.setStatus(Status.USER_STATUS.ACTIVE);
        userRepository.save(userEntity);
        log.info("[user-service] đăng nhập thành công, userId: {}", userEntity.getId());

        return buildAuthenticationResponse(userEntity);
    }

    public AuthenticationResponse handleGoogleOAuthCode(String code) {
        log.info("[user-service] xử lý Google OAuth code");
        if (code == null || code.isBlank()) {
            throw new AppException(ErrorCode.GOOGLE_AUTH_FAILED);
        }

        GoogleTokenResponse tokenResponse;
        try {
            tokenResponse = webClient.post()
                    .uri(googleTokenUri)
                    .contentType(MediaType.APPLICATION_FORM_URLENCODED)
                    .body(BodyInserters.fromFormData("code", code)
                            .with("client_id", googleClientId)
                            .with("client_secret", googleClientSecret)
                            .with("redirect_uri", googleRedirectUri)
                            .with("grant_type", "authorization_code"))
                    .retrieve()
                    .bodyToMono(GoogleTokenResponse.class)
                    .block();
        } catch (Exception exception) {
            log.error("Failed to exchange Google auth code", exception);
            throw new AppException(ErrorCode.GOOGLE_AUTH_FAILED);
        }

        if (tokenResponse == null || tokenResponse.getAccessToken() == null || tokenResponse.getAccessToken().isBlank()) {
            throw new AppException(ErrorCode.GOOGLE_AUTH_FAILED);
        }

        GoogleUserInfoResponse googleUserInfo;
        try {
            googleUserInfo = webClient.get()
                    .uri(googleUserInfoUri)
                    .headers(headers -> headers.setBearerAuth(tokenResponse.getAccessToken()))
                    .retrieve()
                    .bodyToMono(GoogleUserInfoResponse.class)
                    .block();
        } catch (Exception exception) {
            log.error("Failed to load Google user info", exception);
            throw new AppException(ErrorCode.GOOGLE_AUTH_FAILED);
        }

        if (googleUserInfo == null || googleUserInfo.getSub() == null || googleUserInfo.getEmail() == null) {
            throw new AppException(ErrorCode.GOOGLE_AUTH_FAILED);
        }

        UserEntity user = upsertGoogleUser(googleUserInfo);
        user.setLastLoginAt(Instant.now());
        userRepository.save(user);

        return buildAuthenticationResponse(user);
    }

    private UserEntity upsertGoogleUser(GoogleUserInfoResponse googleUserInfo) {
        UserEntity user = userRepository.findByGoogleId(googleUserInfo.getSub())
                .orElseGet(() -> userRepository.findByEmail(googleUserInfo.getEmail()).orElse(null));

        if (user == null) {
            RoleEntity defaultRole = roleRepository.findById(String.valueOf(RoleEnum.USER_FREE))
                    .orElseThrow(() -> new AppException(ErrorCode.ROLE_NOT_FOUND));

            user = UserEntity.builder()
                    .email(googleUserInfo.getEmail())
                    .username(generateUsername(googleUserInfo.getEmail(), googleUserInfo.getSub()))
                    .password(passwordEncoder.encode(UUID.randomUUID().toString()))
                    .googleId(googleUserInfo.getSub())
                    .status(Status.USER_STATUS.VERIFIED)
                    .emailVerified(true)
                    .roles(new HashSet<>(java.util.Set.of(defaultRole)))
                    .build();
            user.setProfile(UserProfileEntity.builder()
                    .fullName(googleUserInfo.getName())
                    .avatarUrl(googleUserInfo.getPicture())
                    .build());
            return userRepository.save(user);
        }

        user.setGoogleId(googleUserInfo.getSub());
        user.setEmail(googleUserInfo.getEmail());
        user.setEmailVerified(true);
        if (user.getStatus() == null) {
            user.setStatus(Status.USER_STATUS.VERIFIED);
        }

        UserProfileEntity profile = user.getProfile();
        if (profile == null) {
            profile = UserProfileEntity.builder().build();
            user.setProfile(profile);
        }
        if (googleUserInfo.getName() != null && !googleUserInfo.getName().isBlank()) {
            profile.setFullName(googleUserInfo.getName());
        }
        if (googleUserInfo.getPicture() != null && !googleUserInfo.getPicture().isBlank()) {
            profile.setAvatarUrl(googleUserInfo.getPicture());
        }

        return user;
    }

    private String generateUsername(String email, String googleId) {
        String base = email != null && email.contains("@")
                ? email.substring(0, email.indexOf('@'))
                : "google_user";
        String normalizedBase = base.replaceAll("[^a-zA-Z0-9_]", "_");
        String candidate = normalizedBase;
        int suffix = 1;

        while (userRepository.findByUsername(candidate).isPresent()) {
            candidate = normalizedBase + "_" + googleId.substring(Math.max(0, googleId.length() - 6)) + "_" + suffix;
            suffix++;
        }

        return candidate;
    }

    public void logout(String token) {
        log.info("[user-service] đăng xuất, vô hiệu hóa token");
        try {
            SignedJWT signToken = verifyToken(token, false);

            String jwtId = signToken.getJWTClaimsSet().getJWTID();
            String userId = signToken.getJWTClaimsSet().getSubject();
            Date expiryTime = signToken.getJWTClaimsSet().getExpirationTime();
            long remainingTime = expiryTime.getTime() - System.currentTimeMillis();

            if (remainingTime > 0) {
                redisTemplate.opsForValue().set(
                        TOKEN_BLACKLIST_PREFIX + userId + "_" + jwtId,
                        "true",
                        remainingTime,
                        TimeUnit.MILLISECONDS);
                log.info("Token {} was blacklisted successfully.", jwtId);
            }
        } catch (ParseException | JOSEException e) {
            log.error("Failed to parse or verify token: {}", e.getMessage());
        } catch (AppException e) {
            log.warn("Token is invalid or expired: {}", e.getMessage());
        }
    }

    public AuthenticationResponse refreshToken(CheckTokenRequest request) throws ParseException, JOSEException {
        if (request.getToken() == null || request.getToken().isBlank()) {
            throw new RuntimeException("Token is empty");
        }
        String token = request.getToken();
        SignedJWT signedJWT = verifyToken(token, true);
        logout(token);

        String userIdStr = signedJWT.getJWTClaimsSet().getSubject();
        UserEntity user = userRepository.findById(UUID.fromString(userIdStr))
                .orElseThrow(() -> new AppException(ErrorCode.UNAUTHENTICATED));
        log.info("[user-service] cấp token mới cho userId: {}", userIdStr);

        return buildAuthenticationResponse(user);
    }

    public void verifyCode(VerifyCodeRequest request) {
        log.info("[user-service] xác thực mã OTP cho email: {}", request.getEmail());
        String email = request.getEmail().trim().toLowerCase();
        UserEntity user = userRepository.findByEmail(email)
                .orElseThrow(() -> new AppException(ErrorCode.USER_NOT_EXISTED));
        String redisKey = "VERIFY_ACCOUNT_" + user.getId() + "_" + request.getCode();

        Boolean hasKey = redisTemplate.hasKey(redisKey);

        if (!hasKey) {
            log.warn("Xác thực thất bại cho email: {}. Mã không tồn tại hoặc hết hạn.", email);
            throw new AppException(ErrorCode.INVALID_CODE_OR_EXPIRED);
        }

        user.setEmailVerified(true);
        user.setStatus(Status.USER_STATUS.VERIFIED);
        userRepository.save(user);
        redisTemplate.delete(redisKey);

        log.info("Xác thực thành công cho User ID: {}", user.getId());
    }

    private String generateUsernameFromEmail(String email) {
        String base = email != null && email.contains("@")
                ? email.substring(0, email.indexOf('@'))
                : "user";
        String normalizedBase = base.replaceAll("[^a-zA-Z0-9_]", "_");
        String candidate = normalizedBase.isBlank() ? "user" : normalizedBase;
        int suffix = 1;

        while (userRepository.findByUsername(candidate).isPresent()) {
            candidate = normalizedBase + "_" + suffix;
            suffix++;
        }

        return candidate;
    }

    private AuthenticationResponse buildAuthenticationResponse(UserEntity userEntity) {
        return AuthenticationResponse.builder()
                .token(generateAccessToken(userEntity))
                .refreshToken(generateRefreshToken(userEntity))
                .build();
    }
}
