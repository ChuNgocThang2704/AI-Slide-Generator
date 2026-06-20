package com.backend.userservice.configuration;

import com.backend.userservice.entity.UserEntity;
import com.backend.userservice.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.domain.AuditorAware;
import org.springframework.data.jpa.repository.config.EnableJpaAuditing;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;

import java.util.Optional;
import java.util.UUID;

@Configuration
@EnableJpaAuditing(auditorAwareRef = "auditorProvider")
@RequiredArgsConstructor
public class AuditConfig {

    private final UserRepository userRepository;

    @Bean
    public AuditorAware<String> auditorProvider() {
        return () -> {
            Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
            if (authentication == null || !authentication.isAuthenticated()
                    || "anonymousUser".equals(authentication.getPrincipal())) {
                return Optional.of("SYSTEM");
            }

            try {
                UUID userId = UUID.fromString(authentication.getName());
                Optional<UserEntity> userEntityOptional = userRepository.findById(userId);
                return userEntityOptional.map(UserEntity::getEmail);
            } catch (IllegalArgumentException e) {
                return Optional.of("UNKNOWN_USER");
            }
        };
    }
}
