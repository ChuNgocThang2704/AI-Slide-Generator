package com.backend.documentservice.repository;

import com.backend.documentservice.entity.ProjectVideo;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface ProjectVideoRepository extends JpaRepository<ProjectVideo, UUID> {
    List<ProjectVideo> findByProjectIdOrderByCreatedAtDesc(UUID projectId);
    Optional<ProjectVideo> findFirstByProjectIdOrderByCreatedAtDesc(UUID projectId);
}
