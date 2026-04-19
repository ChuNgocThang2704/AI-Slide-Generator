package com.backend.documentservice.repository;

import com.backend.documentservice.entity.SourceDocument;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface SourceDocumentRepository extends JpaRepository<SourceDocument, UUID> {
    List<SourceDocument> findByUserId(UUID userId);
}
