package com.backend.documentservice.mapper;

import com.backend.documentservice.dto.response.SlidePageResponse;
import com.backend.documentservice.entity.SlidePage;
import org.mapstruct.Mapper;
import org.mapstruct.ReportingPolicy;

@Mapper(unmappedTargetPolicy = ReportingPolicy.IGNORE, componentModel = "spring")
public interface SlidePageMapper extends EntityMapper<SlidePageResponse, SlidePage> {
}
