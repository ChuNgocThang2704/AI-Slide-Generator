package com.backend.templateservice.mapper;

import com.backend.templateservice.dto.request.CategoryRequest;
import com.backend.templateservice.dto.response.CategoryResponse;
import com.backend.templateservice.entity.Category;

public class CategoryMapper {
    public static CategoryResponse toResponse(Category category) {
        if (category == null) return null;
        return CategoryResponse.builder()
                .id(category.getId())
                .name(category.getName())
                .description(category.getDescription())
                .build();
    }

    public static Category toEntity(CategoryRequest request) {
        if (request == null) return null;
        return Category.builder()
                .name(request.getName())
                .description(request.getDescription())
                .build();
    }
}
