package com.backend.documentservice.service;

import com.backend.documentservice.dto.request.AiConfigSyncRequest;
import com.backend.documentservice.dto.response.AiConfigResponse;
import com.backend.documentservice.entity.AIConfig;
import com.backend.documentservice.exception.AppException;
import com.backend.documentservice.exception.ErrorCode;
import com.backend.documentservice.repository.AiConfigRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Slf4j
public class AiConfigService {

    private final AiConfigRepository aiConfigRepository;

    public List<AiConfigResponse> getAllConfigs() {
        log.info("[document-service] lấy toàn bộ danh sách cấu hình AI");
        return aiConfigRepository.findAll().stream()
                .map(this::toResponse)
                .collect(Collectors.toList());
    }

    @Transactional
    public List<AiConfigResponse> syncConfigs(List<AiConfigSyncRequest> requests) {
        log.info("[document-service] đồng bộ danh sách cấu hình AI, số lượng: {}", requests.size());

        List<AIConfig> currentConfigs = aiConfigRepository.findAll();
        Map<UUID, AIConfig> currentMap = currentConfigs.stream()
                .collect(Collectors.toMap(AIConfig::getId, c -> c));

        List<UUID> requestIds = requests.stream()
                .filter(r -> r.getId() != null)
                .map(AiConfigSyncRequest::getId)
                .collect(Collectors.toList());

        // Delete configs not in request
        List<AIConfig> toDelete = currentConfigs.stream()
                .filter(c -> !requestIds.contains(c.getId()))
                .collect(Collectors.toList());
        if (!toDelete.isEmpty()) {
            aiConfigRepository.deleteAll(toDelete);
        }

        List<AIConfig> toSave = new java.util.ArrayList<>();
        for (AiConfigSyncRequest req : requests) {
            AIConfig config;
            if (req.getId() != null && currentMap.containsKey(req.getId())) {
                // Update
                config = currentMap.get(req.getId());
                updateEntity(config, req);
            } else {
                // Create
                config = AIConfig.builder()
                        .roleCode(req.getRoleCode())
                        .configName(req.getConfigName())
                        .language(req.getLanguage())
                        .tone(req.getTone())
                        .maxProjectsPerDay(req.getMaxProjectsPerDay())
                        .minPagesPerProject(req.getMinPagesPerProject())
                        .maxPagesPerProject(req.getMaxPagesPerProject())
                        .build();
            }
            toSave.add(config);
        }

        return aiConfigRepository.saveAll(toSave).stream()
                .map(this::toResponse)
                .collect(Collectors.toList());
    }

    private void updateEntity(AIConfig entity, AiConfigSyncRequest req) {
        entity.setRoleCode(req.getRoleCode());
        entity.setConfigName(req.getConfigName());
        entity.setLanguage(req.getLanguage());
        entity.setTone(req.getTone());
        entity.setMaxProjectsPerDay(req.getMaxProjectsPerDay());
        entity.setMinPagesPerProject(req.getMinPagesPerProject());
        entity.setMaxPagesPerProject(req.getMaxPagesPerProject());
    }

    private AiConfigResponse toResponse(AIConfig entity) {
        return AiConfigResponse.builder()
                .id(entity.getId())
                .roleCode(entity.getRoleCode())
                .configName(entity.getConfigName())
                .language(entity.getLanguage())
                .tone(entity.getTone())
                .maxProjectsPerDay(entity.getMaxProjectsPerDay())
                .minPagesPerProject(entity.getMinPagesPerProject())
                .maxPagesPerProject(entity.getMaxPagesPerProject())
                .createdAt(entity.getCreatedAt())
                .updatedAt(entity.getUpdatedAt())
                .build();
    }
}
