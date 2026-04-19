package com.backend.documentservice.controller;

import com.backend.documentservice.dto.response.ApiResponse;
import com.backend.documentservice.dto.response.SourceDocumentResponse;
import com.backend.documentservice.service.SourceDocumentService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/source-documents")
@RequiredArgsConstructor
@Slf4j
public class SourceDocumentController {

    private final SourceDocumentService sourceDocumentService;

    @GetMapping
    public ApiResponse<List<SourceDocumentResponse>> getAll() {
        UUID userId = UUID.fromString(SecurityContextHolder.getContext().getAuthentication().getName());
        return ApiResponse.<List<SourceDocumentResponse>>builder()
                .data(sourceDocumentService.getDocumentsByUser(userId))
                .build();
    }

    @GetMapping("/{id}")
    public ApiResponse<SourceDocumentResponse> getById(@PathVariable UUID id) {
        UUID userId = UUID.fromString(SecurityContextHolder.getContext().getAuthentication().getName());
        return ApiResponse.<SourceDocumentResponse>builder()
                .data(sourceDocumentService.getDocument(id, userId))
                .build();
    }

    @DeleteMapping
    public ApiResponse<String> delete(@RequestBody List<UUID> ids) {
        UUID userId = UUID.fromString(SecurityContextHolder.getContext().getAuthentication().getName());
        sourceDocumentService.deleteDocuments(ids, userId);
        return ApiResponse.<String>builder()
                .data("Documents deleted successfully")
                .build();
    }
}
