package com.backend.userservice.configuration;


import com.backend.userservice.dto.request.CheckTokenRequest;
import com.backend.userservice.dto.response.CheckTokenResponse;
import com.backend.userservice.service.AuthenticationService;
import com.nimbusds.jwt.SignedJWT;
import lombok.RequiredArgsConstructor;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtException;
import org.springframework.stereotype.Component;

import java.text.ParseException;

@Component
@RequiredArgsConstructor
public class CustomJwtDecoder implements JwtDecoder {
    private final AuthenticationService authenticationService;

    @Override
    public Jwt decode(String token) throws JwtException {
        try {
            CheckTokenResponse response = authenticationService.checkValidToken(CheckTokenRequest.builder().token(token).build());
            if(!response.isValid()){
                throw new JwtException("Invalid token");
            }
            SignedJWT signedJWT = SignedJWT.parse(token);

            return new Jwt(token,
                    signedJWT.getJWTClaimsSet().getIssueTime().toInstant(),
                    signedJWT.getJWTClaimsSet().getExpirationTime().toInstant(),
                    signedJWT.getHeader().toJSONObject(),
                    signedJWT.getJWTClaimsSet().getClaims()
            );

        } catch (ParseException e) {
            throw new JwtException("Invalid token");
        }
    }
}
