package com.backend.templateservice.controller;

import com.backend.templateservice.dto.request.TemplateRequest;
import com.backend.templateservice.dto.response.ApiResponse;
import com.backend.templateservice.dto.response.PageResponse;
import com.backend.templateservice.dto.response.TemplateResponse;
import com.backend.templateservice.service.TemplateService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping
@RequiredArgsConstructor
public class TemplateController {

    private final TemplateService templateService;

    @PostMapping(value = "/upload", consumes = "multipart/form-data")
    public ApiResponse<Map<String, Object>> uploadFile(@RequestParam("file") MultipartFile file) {
        return ApiResponse.<Map<String, Object>>builder()
                .data(templateService.uploadFileOnly(file))
                .build();
    }

    @PostMapping("/save")
    public ApiResponse<TemplateResponse> saveTemplate(@RequestBody TemplateRequest request) {
        return ApiResponse.<TemplateResponse>builder()
                .data(templateService.saveTemplate(request))
                .build();
    }

    @GetMapping("/get-all")
    public ApiResponse<PageResponse<TemplateResponse>> getAllTemplates(
            @RequestParam(required = false) String search,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "10") int size
    ) {
        return ApiResponse.<PageResponse<TemplateResponse>>builder()
                .data(templateService.getAllTemplates(search, page, size))
                .build();
    }

    @GetMapping("/public")
    public ApiResponse<PageResponse<TemplateResponse>> getPublicTemplates(
            @RequestParam(required = false) String search,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "10") int size
    ) {
        return ApiResponse.<PageResponse<TemplateResponse>>builder()
                .data(templateService.getAllTemplates(search, page, size))
                .build();
    }

    @GetMapping("/{id}")
    public ApiResponse<TemplateResponse> getTemplate(@PathVariable UUID id) {
        return ApiResponse.<TemplateResponse>builder()
                .data(templateService.getTemplate(id))
                .build();
    }

    @GetMapping("/{id}/view")
    public ApiResponse<String> getPresignedViewUrl(@PathVariable UUID id) {
        return ApiResponse.<String>builder()
                .data(templateService.getPresignedViewUrl(id))
                .build();
    }

    @DeleteMapping("/delete")
    public ApiResponse<Void> deleteTemplates(@RequestBody List<UUID> ids) {
        templateService.deleteTemplates(ids);
        return ApiResponse.<Void>builder().build();
    }
}
