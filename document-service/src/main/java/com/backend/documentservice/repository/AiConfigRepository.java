package com.backend.documentservice.repository;

import com.backend.documentservice.entity.AIConfig;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

@Repository
public interface AiConfigRepository extends JpaRepository<AIConfig, UUID> {
    Optional<AIConfig> findByRoleCode(String roleCode);
}
