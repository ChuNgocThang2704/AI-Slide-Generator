package com.backend.documentservice.mapper;

import com.backend.documentservice.dto.response.SourceDocumentResponse;
import com.backend.documentservice.entity.SourceDocument;
import org.mapstruct.Mapper;
import org.mapstruct.ReportingPolicy;

@Mapper(unmappedTargetPolicy = ReportingPolicy.IGNORE, componentModel = "spring")
public interface SourceDocumentMapper extends EntityMapper<SourceDocumentResponse, SourceDocument> {
}
