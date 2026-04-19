package com.backend.documentservice.repository;

import com.backend.documentservice.entity.AiConfig;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

@Repository
public interface AiConfigRepository extends JpaRepository<AiConfig, UUID> {
    Optional<AiConfig> findByRoleCode(String roleCode);
}
