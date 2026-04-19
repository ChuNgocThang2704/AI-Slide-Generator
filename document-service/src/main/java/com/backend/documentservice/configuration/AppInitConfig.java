package com.backend.documentservice.configuration;

import com.backend.documentservice.entity.AiConfig;
import com.backend.documentservice.repository.AiConfigRepository;
import com.backend.documentservice.util.Constants;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
@RequiredArgsConstructor
@Slf4j
public class AppInitConfig {

    @Bean
    ApplicationRunner applicationRunner(AiConfigRepository aiConfigRepository) {
        return args -> {
            log.info("Initializing AI Configurations...");

            // USER_FREE Configuration
            createConfigIfNotExist(aiConfigRepository, Constants.USER_ROLES.USER_FREE, "Gói Miễn phí", 
                    "Tiếng Việt", "Chuyên nghiệp", 3, 3, 10);

            // USER_PRO Configuration
            createConfigIfNotExist(aiConfigRepository, Constants.USER_ROLES.USER_PRO, "Gói Chuyên nghiệp", 
                    "Tiếng Việt", "Sáng tạo", 20, 5, 30);

            // USER_EXTRA Configuration
            createConfigIfNotExist(aiConfigRepository, Constants.USER_ROLES.USER_EXTRA, "Gói Đặc biệt", 
                    "Tiếng Việt", "Hàn lâm", 999, 1, 100);

            // ADMIN Configuration
            createConfigIfNotExist(aiConfigRepository, Constants.USER_ROLES.ADMIN, "Cấu hình Hệ thống", 
                    "Tiếng Việt", "Chuyên nghiệp", 999, 1, 100);

            log.info("AI Configurations initialization completed.");
        };
    }

    private void createConfigIfNotExist(AiConfigRepository repository, String roleCode, String configName, 
                                        String lang, String tone, int maxDay, int minPage, int maxPage) {
        if (repository.findByRoleCode(roleCode).isEmpty()) {
            AiConfig config = AiConfig.builder()
                    .roleCode(roleCode)
                    .configName(configName)
                    .language(lang)
                    .tone(tone)
                    .maxProjectsPerDay(maxDay)
                    .minPagesPerProject(minPage)
                    .maxPagesPerProject(maxPage)
                    .build();
            repository.save(config);
            log.info(">>> Created AI Config for: {}", roleCode);
        }
    }
}
