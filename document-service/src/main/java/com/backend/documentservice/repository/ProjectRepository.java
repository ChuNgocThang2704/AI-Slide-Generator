package com.backend.documentservice.repository;

import com.backend.documentservice.entity.Project;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.UUID;

@Repository
public interface ProjectRepository extends JpaRepository<Project, UUID> {
    Page<Project> findByOwnerIdAndNameContainingIgnoreCase(UUID ownerId, String name, Pageable pageable);
    Page<Project> findByOwnerId(UUID ownerId, Pageable pageable);
}
