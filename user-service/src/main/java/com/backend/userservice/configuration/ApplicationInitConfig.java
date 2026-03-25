package com.backend.userservice.configuration;

import com.backend.userservice.constant.RoleEnum;
import com.backend.userservice.entity.RoleEntity;
import com.backend.userservice.entity.UserEntity;
import com.backend.userservice.exception.AppException;
import com.backend.userservice.exception.ErrorCode;
import com.backend.userservice.repository.RoleRepository;
import com.backend.userservice.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.experimental.NonFinal;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.crypto.password.PasswordEncoder;

import java.util.HashSet;
import java.util.Set;

@Configuration
@RequiredArgsConstructor
@Slf4j
public class ApplicationInitConfig {

    private final PasswordEncoder passwordEncoder;

    @NonFinal
    static final String ADMIN_USER_NAME = "admin";

    @NonFinal
    static final String ADMIN_PASSWORD = "admin";

    @Bean
    ApplicationRunner applicationRunner(UserRepository userRepository, RoleRepository roleRepository){
        log.info("Start initializing application... ");
        return args -> {
            String adminEmail = "admin@aislide.com";
            if (userRepository.findByEmail(adminEmail).isEmpty()) {
                RoleEntity adminRole = roleRepository.findByName("ADMIN")
                        .orElseGet(() -> roleRepository.save(RoleEntity.builder().name("ADMIN").build()));

                roleRepository.findByName("USER")
                        .orElseGet(() -> roleRepository.save(RoleEntity.builder().name("USER").build()));

                UserEntity admin = UserEntity.builder()
                        .email(adminEmail)
                        .username(ADMIN_USER_NAME)
                        .password(passwordEncoder.encode(ADMIN_PASSWORD))
                        .roles(Set.of(adminRole))
                        .build();
                userRepository.save(admin);
                log.warn("Admin account created: admin@aislide.com / admin123");
            }
            log.info("Application initialized successfully...");
        };
    }
}
