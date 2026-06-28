package com.backend.templateservice.service;

import com.backend.templateservice.dto.request.CategoryRequest;
import com.backend.templateservice.dto.response.CategoryResponse;
import com.backend.templateservice.dto.response.PageResponse;
import com.backend.templateservice.entity.Category;
import com.backend.templateservice.exception.CustomException;
import com.backend.templateservice.exception.ErrorCode;
import com.backend.templateservice.mapper.CategoryMapper;
import com.backend.templateservice.repository.CategoryRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class CategoryService {

    private final CategoryRepository categoryRepository;

    @Transactional
    public CategoryResponse saveCategory(CategoryRequest request) {
        Category category;
        if (request.getId() != null) {
            category = categoryRepository.findById(request.getId())
                    .orElseThrow(() -> new CustomException(ErrorCode.CATEGORY_NOT_FOUND));
            category.setName(request.getName());
            category.setDescription(request.getDescription());
        } else {
            if (categoryRepository.existsByName(request.getName())) {
                throw new CustomException(ErrorCode.UNCATEGORIZED_EXCEPTION);
            }
            category = CategoryMapper.toEntity(request);
        }
        category = categoryRepository.save(category);
        return CategoryMapper.toResponse(category);
    }

    @Transactional
    public void deleteCategories(List<UUID> ids) {
        if (ids == null || ids.isEmpty()) {
            return;
        }
        List<Category> categories = categoryRepository.findAllById(ids);
        if (!categories.isEmpty()) {
            categoryRepository.deleteAll(categories);
        }
    }

    public CategoryResponse getCategory(UUID id) {
        Category category = categoryRepository.findById(id)
                .orElseThrow(() -> new CustomException(ErrorCode.CATEGORY_NOT_FOUND));
        return CategoryMapper.toResponse(category);
    }

    public PageResponse<CategoryResponse> getAllCategories(String search, int page, int size) {
        Page<Category> categoryPage = categoryRepository.searchCategories(
                search,
                PageRequest.of(page, size, Sort.by("createdAt").descending())
        );

        return PageResponse.<CategoryResponse>builder()
                .page(categoryPage.getNumber())
                .size(categoryPage.getSize())
                .totalElements(categoryPage.getTotalElements())
                .totalPages(categoryPage.getTotalPages())
                .items(categoryPage.getContent().stream()
                        .map(CategoryMapper::toResponse)
                        .collect(Collectors.toList()))
                .build();
    }
}
