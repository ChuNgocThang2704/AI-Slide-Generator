package com.backend.templateservice.controller;

import com.backend.templateservice.dto.request.TemplateRequest;
import com.backend.templateservice.dto.request.TemplateMatchRequest;
import com.backend.templateservice.dto.response.ApiResponse;
import com.backend.templateservice.dto.response.PageResponse;
import com.backend.templateservice.dto.response.TemplateResponse;
import com.backend.templateservice.dto.response.TemplateMatchResponse;
import com.backend.templateservice.dto.response.TemplateImportResponse;
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

    @PostMapping(value = "/custom", consumes = "multipart/form-data")
    public ApiResponse<TemplateResponse> uploadCustomTemplate(
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "name", required = false) String name
    ) {
        return ApiResponse.<TemplateResponse>builder()
                .data(templateService.uploadCustomTemplate(file, name))
                .build();
    }

    @PostMapping(value = "/import", consumes = "multipart/form-data")
    public ApiResponse<TemplateImportResponse> importSlides(@RequestParam("file") MultipartFile file) {
        return ApiResponse.<TemplateImportResponse>builder()
                .data(templateService.importSlides(file))
                .build();
    }

    @PostMapping("/{id}/match")
    public ApiResponse<TemplateMatchResponse> matchLayout(
            @PathVariable UUID id,
            @RequestBody TemplateMatchRequest request
    ) {
        return ApiResponse.<TemplateMatchResponse>builder()
                .data(templateService.matchLayout(id, request))
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

    @PostMapping("/custom/generated")
    public ApiResponse<TemplateResponse> saveGeneratedTheme(@RequestBody java.util.Map<String, String> body) {
        return ApiResponse.<TemplateResponse>builder()
                .data(templateService.saveGeneratedTheme(body.get("name"), body.get("code")))
                .build();
    }

    @PostMapping("/custom/{id}/reparse")
    public ApiResponse<TemplateResponse> reparseCustomTemplate(@PathVariable UUID id) {
        return ApiResponse.<TemplateResponse>builder()
                .data(templateService.reparseCustomTemplate(id))
                .build();
    }

    @GetMapping("/public/assets/{id}/{name}")
    public org.springframework.http.ResponseEntity<byte[]> getTemplateAsset(@PathVariable UUID id, @PathVariable String name) {
        byte[] data = templateService.getAssetBytes(id, name);
        if (data == null) return org.springframework.http.ResponseEntity.notFound().build();
        return org.springframework.http.ResponseEntity.ok()
                .contentType(org.springframework.http.MediaType.parseMediaType(com.backend.templateservice.service.PowerPointTemplateParser.contentTypeFor(name)))
                .cacheControl(org.springframework.http.CacheControl.maxAge(java.time.Duration.ofDays(7)).cachePublic())
                .body(data);
    }

    @GetMapping("/public")
    public ApiResponse<PageResponse<TemplateResponse>> getPublicTemplates(
            @RequestParam(required = false) String search,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "10") int size
    ) {
        return ApiResponse.<PageResponse<TemplateResponse>>builder()
                .data(templateService.getPublicTemplates(search, page, size))
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

    @DeleteMapping("/custom/{id}")
    public ApiResponse<Void> deleteCustomTemplate(@PathVariable UUID id) {
        templateService.deleteCustomTemplate(id);
        return ApiResponse.<Void>builder().build();
    }
}
