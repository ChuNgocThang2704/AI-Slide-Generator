package com.backend.templateservice.service;

import com.backend.templateservice.dto.request.TemplateMatchRequest;
import com.backend.templateservice.entity.Template;
import com.backend.templateservice.exception.CustomException;
import com.backend.templateservice.exception.ErrorCode;
import com.backend.templateservice.repository.CategoryRepository;
import com.backend.templateservice.repository.TemplateRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.AuditorAware;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.Pageable;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class TemplateServiceOwnershipTest {

    @Mock
    private TemplateRepository templateRepository;
    @Mock
    private CategoryRepository categoryRepository;
    @Mock
    private S3Service s3Service;
    @Mock
    private PowerPointTemplateParser templateParser;
    @Mock
    private TemplateLayoutMatcher layoutMatcher;
    @Mock
    private AuditorAware<String> auditorProvider;

    private TemplateService templateService;

    @BeforeEach
    void setUp() {
        lenient().when(auditorProvider.getCurrentAuditor()).thenReturn(Optional.of("owner@example.com"));
        templateService = new TemplateService(
                templateRepository,
                categoryRepository,
                s3Service,
                templateParser,
                layoutMatcher,
                new ObjectMapper(),
                auditorProvider
        );
    }

    @Test
    void listsOnlySharedTemplatesAndCustomTemplatesOwnedByCurrentUser() {
        when(templateRepository.searchVisibleTemplates(isNull(), eq("owner@example.com"), org.mockito.ArgumentMatchers.any(Pageable.class)))
                .thenReturn(new PageImpl<>(List.of()));

        templateService.getAllTemplates(null, 0, 10);

        verify(templateRepository).searchVisibleTemplates(
                isNull(),
                eq("owner@example.com"),
                org.mockito.ArgumentMatchers.any(Pageable.class)
        );
    }

    @Test
    void rejectsMatchingAnotherUsersCustomTemplate() {
        UUID templateId = UUID.randomUUID();
        Template template = new Template();
        template.setId(templateId);
        template.setSourceType("CUSTOM_PPTX");
        template.setCreatedBy("other@example.com");
        when(templateRepository.findById(templateId)).thenReturn(Optional.of(template));

        assertThatThrownBy(() -> templateService.matchLayout(templateId, new TemplateMatchRequest()))
                .isInstanceOf(CustomException.class)
                .extracting("errorCode")
                .isEqualTo(ErrorCode.TEMPLATE_NOT_FOUND);

        verify(layoutMatcher, never()).match(org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any());
    }

    @Test
    void publicListExcludesEveryCustomTemplate() {
        when(templateRepository.searchPublicTemplates(isNull(), org.mockito.ArgumentMatchers.any(Pageable.class)))
                .thenReturn(new PageImpl<>(List.of()));

        templateService.getPublicTemplates(null, 0, 10);

        verify(templateRepository).searchPublicTemplates(
                isNull(),
                org.mockito.ArgumentMatchers.any(Pageable.class)
        );
    }
}
