package com.backend.documentservice.mapper;

import com.backend.documentservice.dto.request.ProjectCreateRequest;
import com.backend.documentservice.dto.response.ProjectResponse;
import com.backend.documentservice.entity.Project;
import org.mapstruct.Mapper;
import org.mapstruct.MappingTarget;
import org.mapstruct.ReportingPolicy;

import org.mapstruct.Mapping;

@Mapper(unmappedTargetPolicy = ReportingPolicy.IGNORE, componentModel = "spring")
public interface ProjectMapper extends EntityMapper<ProjectResponse, Project> {
    @Override
    @Mapping(source = "createdAt", target = "createdAt")
    @Mapping(source = "updatedAt", target = "updatedAt")
    ProjectResponse toDto(Project entity);
    
    void updateEntityFromRequest(ProjectCreateRequest request, @MappingTarget Project entity);
}
