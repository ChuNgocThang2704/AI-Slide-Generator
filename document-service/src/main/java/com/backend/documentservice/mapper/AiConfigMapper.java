package com.backend.documentservice.mapper;

import com.backend.documentservice.dto.response.AiConfigResponse;
import com.backend.documentservice.entity.AiConfig;
import org.mapstruct.Mapper;
import org.mapstruct.ReportingPolicy;

@Mapper(unmappedTargetPolicy = ReportingPolicy.IGNORE, componentModel = "spring")
public interface AiConfigMapper extends EntityMapper<AiConfigResponse, AiConfig> {
}
