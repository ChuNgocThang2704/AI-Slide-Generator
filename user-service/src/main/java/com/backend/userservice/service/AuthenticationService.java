package com.backend.userservice.service;

import com.backend.userservice.dto.request.AuthenticationRequest;
import com.backend.userservice.dto.response.AuthenticationResponse;
import com.backend.userservice.entity.UserEntity;
import com.backend.userservice.exception.AppException;
import com.backend.userservice.exception.ErrorCode;
import com.backend.userservice.repository.UserRepository;
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
import java.util.Date;
import java.util.StringJoiner;
import java.util.UUID;
import java.util.concurrent.TimeUnit;
import lombok.RequiredArgsConstructor;
import lombok.experimental.NonFinal;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.util.CollectionUtils;

@Service
@RequiredArgsConstructor
@Slf4j
public class AuthenticationService {
    private static final String TOKEN_BLACKLIST_PREFIX = "TOKEN_BLACK_LIST_";

    private final UserRepository userRepository;
    private final RedisTemplate<String, Object> redisTemplate;

    @NonFinal
    @Value("${jwt.signerKey}")
    protected String SIGNER_KEY;

    @NonFinal
    @Value("${jwt.valid-duration}")
    protected long VALID_DURATION;

    @NonFinal
    @Value("${jwt.refreshable-duration}")
    protected long REFRESHABLE_DURATION;

    private SignedJWT verifyToken(String token, boolean isRefresh) throws JOSEException, ParseException {
        JWSVerifier jwsVerifier = new MACVerifier(SIGNER_KEY.getBytes());
        SignedJWT signedJWT = SignedJWT.parse(token);

        Date expiryTime = isRefresh
                ? new Date(signedJWT.getJWTClaimsSet()
                        .getIssueTime()
                        .toInstant()
                        .plus(REFRESHABLE_DURATION, ChronoUnit.SECONDS)
                        .toEpochMilli())
                : signedJWT.getJWTClaimsSet().getExpirationTime();

        boolean verified = signedJWT.verify(jwsVerifier);
        if (!verified || expiryTime.before(new Date())) {
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
                if (!CollectionUtils.isEmpty(role.getPermissions())) {
                    role.getPermissions().forEach(permission -> stringJoiner.add(permission.getName()));
                }
            });
        }

        return stringJoiner.toString();
    }

    private String generateToken(UserEntity userEntity) {
        JWSHeader jwsHeader = new JWSHeader(JWSAlgorithm.HS512);

        JWTClaimsSet jwtClaimsSet = new JWTClaimsSet.Builder()
                .subject(userEntity.getId().toString())
                .issuer("ai-slide-generator")
                .issueTime(new Date())
                .expirationTime(new Date(Instant.now().plus(VALID_DURATION, ChronoUnit.SECONDS).toEpochMilli()))
                .jwtID(UUID.randomUUID().toString())
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

    public AuthenticationResponse authenticate(AuthenticationRequest request) {
        PasswordEncoder passwordEncoder = new BCryptPasswordEncoder(10);
        UserEntity userEntity = userRepository
                .findByUsername(request.getUsername())
                .orElseThrow(() -> new AppException(ErrorCode.USER_NOT_EXISTED));

        boolean authenticated = passwordEncoder.matches(request.getPassword(), userEntity.getPassword());
        if (!authenticated) {
            throw new AppException(ErrorCode.USERNAME_OR_PASSWORD_INCORRECT);
        }

        return AuthenticationResponse.builder()
                .token(generateToken(userEntity))
                .build();
    }

    public void logout(String token) {
        try {
            SignedJWT signToken = verifyToken(token, true);

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

    public AuthenticationResponse refreshToken(String token) throws ParseException, JOSEException {
        SignedJWT signedJWT = verifyToken(token, true);
        logout(token);

        String userIdStr = signedJWT.getJWTClaimsSet().getSubject();
        UserEntity user = userRepository.findById(UUID.fromString(userIdStr))
                .orElseThrow(() -> new AppException(ErrorCode.UNAUTHENTICATED));

        return AuthenticationResponse.builder()
                .token(generateToken(user))
                .build();
    }
}
