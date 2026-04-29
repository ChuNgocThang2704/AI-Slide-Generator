package com.backend.documentservice.mapper;

import com.backend.documentservice.dto.response.SourceDocumentResponse;
import com.backend.documentservice.entity.SourceDocument;
import org.mapstruct.Mapper;
import org.mapstruct.ReportingPolicy;

import org.mapstruct.Mapping;

@Mapper(unmappedTargetPolicy = ReportingPolicy.IGNORE, componentModel = "spring")
public interface SourceDocumentMapper extends EntityMapper<SourceDocumentResponse, SourceDocument> {
    @Override
    @Mapping(source = "createdAt", target = "createdAt")
    @Mapping(source = "updatedAt", target = "updatedAt")
    SourceDocumentResponse toDto(SourceDocument entity);
}
