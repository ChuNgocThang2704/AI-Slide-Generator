package com.backend.templateservice.controller;

import com.backend.templateservice.dto.request.CategoryRequest;
import com.backend.templateservice.dto.response.ApiResponse;
import com.backend.templateservice.dto.response.CategoryResponse;
import com.backend.templateservice.dto.response.PageResponse;
import com.backend.templateservice.service.CategoryService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/categories")
@RequiredArgsConstructor
public class CategoryController {

    private final CategoryService categoryService;

    @PostMapping
    public ApiResponse<CategoryResponse> saveCategory(@RequestBody CategoryRequest request) {
        return ApiResponse.<CategoryResponse>builder()
                .data(categoryService.saveCategory(request))
                .build();
    }

    @GetMapping
    public ApiResponse<PageResponse<CategoryResponse>> getAllCategories(
            @RequestParam(required = false) String search,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "10") int size
    ) {
        return ApiResponse.<PageResponse<CategoryResponse>>builder()
                .data(categoryService.getAllCategories(search, page, size))
                .build();
    }

    @GetMapping("/{id}")
    public ApiResponse<CategoryResponse> getCategory(@PathVariable UUID id) {
        return ApiResponse.<CategoryResponse>builder()
                .data(categoryService.getCategory(id))
                .build();
    }

    @DeleteMapping
    public ApiResponse<Void> deleteCategories(@RequestBody List<UUID> ids) {
        categoryService.deleteCategories(ids);
        return ApiResponse.<Void>builder().build();
    }
}
