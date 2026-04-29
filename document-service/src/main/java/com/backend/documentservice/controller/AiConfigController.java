package com.backend.documentservice.controller;

import com.backend.documentservice.dto.request.AiConfigSyncRequest;
import com.backend.documentservice.dto.response.AiConfigResponse;
import com.backend.documentservice.dto.response.ApiResponse;
import com.backend.documentservice.service.AiConfigService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/admin/ai-configs")
@RequiredArgsConstructor
@Slf4j
public class AiConfigController {

    private final AiConfigService aiConfigService;

    @GetMapping
    @PreAuthorize("hasAnyRole('ADMIN')")
    public ApiResponse<List<AiConfigResponse>> getAllConfigs() {
        return ApiResponse.<List<AiConfigResponse>>builder()
                .data(aiConfigService.getAllConfigs())
                .build();
    }

    @PostMapping("/sync")
    @PreAuthorize("hasAnyRole('ADMIN')")
    public ApiResponse<List<AiConfigResponse>> syncConfigs(@RequestBody @Valid List<AiConfigSyncRequest> requests) {
        return ApiResponse.<List<AiConfigResponse>>builder()
                .data(aiConfigService.syncConfigs(requests))
                .build();
    }
}
