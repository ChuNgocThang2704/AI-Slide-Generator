package com.backend.documentservice.configuration;

import feign.RequestInterceptor;
import feign.RequestTemplate;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Bean;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;

@Slf4j
public class FeignClientConfig {

    @Bean
    public RequestInterceptor requestInterceptor() {
        return new RequestInterceptor() {
            @Override
            public void apply(RequestTemplate template) {
                Authentication auth = SecurityContextHolder.getContext().getAuthentication();
                if (auth instanceof JwtAuthenticationToken jwtAuth) {
                    String tokenValue = jwtAuth.getToken().getTokenValue();
                    template.header("Authorization", "Bearer " + tokenValue);
                    log.debug("[document-service] Feign RequestInterceptor: Forwarding JWT token successfully.");
                } else {
                    log.warn("[document-service] Feign RequestInterceptor: No active JWT token found in SecurityContext.");
                }
            }
        };
    }
}
