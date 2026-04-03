package com.backend.userservice.configuration;

import com.backend.userservice.constant.RoleEnum;
import com.backend.userservice.entity.PermissionEntity;
import com.backend.userservice.entity.RoleEntity;
import com.backend.userservice.entity.UserEntity;
import com.backend.userservice.entity.UserProfileEntity;
import com.backend.userservice.repository.PermissionRepository;
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

import java.util.Set;

@Configuration
@RequiredArgsConstructor
@Slf4j
public class ApplicationInitConfig {

    private final PasswordEncoder passwordEncoder;
    private final PermissionRepository permissionRepository;
    @NonFinal
    static final String ADMIN_USER_NAME = "admin";

    @NonFinal
    static final String ADMIN_PASSWORD = "admin123";

    @Bean
    ApplicationRunner applicationRunner(UserRepository userRepository, RoleRepository roleRepository){
        log.info("Start initializing application... ");
        return args -> {
            PermissionEntity genBasic = createPermissionIfNotExist("GENERATE_SLIDE_BASIC", "Tạo slide cơ bản (3 slide/ngày)");
            PermissionEntity genPro = createPermissionIfNotExist("GENERATE_SLIDE_PRO", "Tạo slide nâng cao (20 slide/ngày)");
            PermissionEntity genUltra = createPermissionIfNotExist("GENERATE_SLIDE_ULTRA", "Tạo slide không giới hạn");

            PermissionEntity imgSD = createPermissionIfNotExist("GENERATE_IMAGE_SD", "Gen ảnh chất lượng SD (tiết kiệm)");
            PermissionEntity imgHd = createPermissionIfNotExist("GENERATE_IMAGE_HD", "Gen ảnh chất lượng HD (tốt)");
            PermissionEntity imgUltra = createPermissionIfNotExist("GENERATE_IMAGE_ULTRA", "Gen ảnh chất lượng Ultra (best)");

            PermissionEntity exportPdf = createPermissionIfNotExist("EXPORT_PDF", "Xuất file PDF");
            PermissionEntity customTemplate = createPermissionIfNotExist("CUSTOM_TEMPLATE", "Sử dụng mẫu slide tùy chỉnh");
            PermissionEntity viewHistory = createPermissionIfNotExist("VIEW_HISTORY", "Xem lịch sử tạo slide");

            // 2. Khởi tạo và Gán quyền cho các Role

            // ROLE ADMIN: Full quyền
            RoleEntity adminRole = roleRepository.findByName("ADMIN").orElseGet(() ->
                    roleRepository.save(RoleEntity.builder()
                            .name("ADMIN")
                            .description("Quản trị viên hệ thống")
                            .permissions(Set.of(genUltra, imgUltra, exportPdf, customTemplate, viewHistory))
                            .build()));

            // ROLE USER_FREE: 3 slide/ngày, ảnh SD
            roleRepository.findByName("USER_FREE").orElseGet(() ->
                    roleRepository.save(RoleEntity.builder()
                            .name("USER_FREE")
                            .description("Người dùng miễn phí")
                            .permissions(Set.of(genBasic, imgSD, viewHistory))
                            .build()));

            // ROLE USER_PRO: 20 slide/ngày, ảnh HD, Export PDF
            roleRepository.findByName("USER_PRO").orElseGet(() ->
                    roleRepository.save(RoleEntity.builder()
                            .name("USER_PRO")
                            .description("Người dùng chuyên nghiệp")
                            .permissions(Set.of(genPro, imgHd, exportPdf, viewHistory))
                            .build()));

            // ROLE USER_EXTRA: Không giới hạn, Ưu tiên cao
            roleRepository.findByName("USER_EXTRA").orElseGet(() ->
                    roleRepository.save(RoleEntity.builder()
                            .name("USER_EXTRA")
                            .description("Người dùng đặc biệt")
                            .permissions(Set.of(genUltra, imgUltra, exportPdf, customTemplate, viewHistory))
                            .build()));

            // 3. Khởi tạo tài khoản Admin mẫu
            String adminEmail = "admin@aislide.com";
            if (userRepository.findByEmail(adminEmail).isEmpty()) {
                UserEntity admin = UserEntity.builder()
                        .email(adminEmail)
                        .username(ADMIN_USER_NAME)
                        .password(passwordEncoder.encode(ADMIN_PASSWORD))
                        .emailVerified(true)
                        .roles(Set.of(adminRole))
                        .build();

                admin.setProfile(UserProfileEntity.builder()
                        .fullName("System Administrator")
                        .build());

                userRepository.save(admin);
                log.warn(">>> ADMIN ACCOUNT CREATED: admin@aislide.com / admin123");
            }

            log.info("System data initialization completed successfully.");
        };
    }

    private PermissionEntity createPermissionIfNotExist(String name, String desc) {
        return permissionRepository.findById(name)
                .orElseGet(() -> permissionRepository.save(
                        PermissionEntity.builder().name(name).description(desc).build()
                ));
    }
}
