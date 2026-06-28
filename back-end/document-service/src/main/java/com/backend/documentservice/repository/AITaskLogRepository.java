package com.backend.documentservice.repository;

import com.backend.documentservice.entity.AITaskLog;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface AITaskLogRepository extends JpaRepository<AITaskLog, UUID> {
    List<AITaskLog> findByProjectId(UUID projectId);
}
