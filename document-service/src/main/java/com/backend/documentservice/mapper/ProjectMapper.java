package com.backend.documentservice.mapper;

import com.backend.documentservice.dto.request.ProjectCreateRequest;
import com.backend.documentservice.dto.response.ProjectResponse;
import com.backend.documentservice.entity.Project;
import org.mapstruct.Mapper;
import org.mapstruct.MappingTarget;
import org.mapstruct.ReportingPolicy;

@Mapper(unmappedTargetPolicy = ReportingPolicy.IGNORE, componentModel = "spring")
public interface ProjectMapper extends EntityMapper<ProjectResponse, Project> {
    
    void updateEntityFromRequest(ProjectCreateRequest request, @MappingTarget Project entity);
}
