package com.backend.documentservice.repository;

import com.backend.documentservice.entity.SourceDocument;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.UUID;

@Repository
public interface SourceDocumentRepository extends JpaRepository<SourceDocument, UUID> {
    Page<SourceDocument> findByUserIdAndFileNameContainingIgnoreCase(UUID userId, String fileName, Pageable pageable);
    Page<SourceDocument> findByUserId(UUID userId, Pageable pageable);
}
