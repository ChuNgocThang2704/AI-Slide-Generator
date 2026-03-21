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
    @ConditionalOnProperty(
            prefix = "spring",
            value = "datasource.driverClassName",
            havingValue = "com.mysql.cj.jdbc.Driver")
    ApplicationRunner applicationRunner(UserRepository userRepository, RoleRepository roleRepository){
        log.info("Start initializing application... ");
        return args -> {
            if (userRepository.findByUsername(ADMIN_USER_NAME).isEmpty()) {
                if (roleRepository.findById(String.valueOf(RoleEnum.USER)).isEmpty()) {
                    roleRepository.save(RoleEntity.builder()
                            .name(String.valueOf(RoleEnum.USER))
                            .description("Role User")
                            .build());
                }
                if (roleRepository.findById(String.valueOf(RoleEnum.ADMIN)).isEmpty()) {
                    roleRepository.save(RoleEntity.builder()
                            .name(String.valueOf(RoleEnum.ADMIN))
                            .description("Role Admin")
                            .build());
                }
                RoleEntity roleAdmin = roleRepository.findById(String.valueOf(RoleEnum.ADMIN))
                        .orElseThrow(() -> new AppException(ErrorCode.ROLE_NOT_FOUND));

                Set<RoleEntity> roles = new HashSet<>();
                roles.add(roleAdmin);

                UserEntity user = UserEntity.builder()
                        .username(ADMIN_USER_NAME)
                        .password(passwordEncoder.encode(ADMIN_PASSWORD))
                        .roles(roles)
                        .build();
                userRepository.save(user);
                log.warn("Admin user has been created with default password: admin, please change it!!!");
            }
            log.info("Application initialized successfully...");
        };
    }
}
