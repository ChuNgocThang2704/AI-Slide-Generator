package com.backend.templateservice.repository;

import com.backend.templateservice.entity.Template;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.UUID;

@Repository
public interface TemplateRepository extends JpaRepository<Template, UUID> {

    @Query("""
            SELECT t FROM Template t
            WHERE (t.sourceType IS NULL OR t.sourceType <> 'CUSTOM_PPTX' OR t.createdBy = :owner)
              AND (:search IS NULL OR :search = ''
                OR LOWER(t.name) LIKE LOWER(CONCAT('%', :search, '%'))
                OR LOWER(t.description) LIKE LOWER(CONCAT('%', :search, '%')))
            """)
    Page<Template> searchVisibleTemplates(
            @Param("search") String search,
            @Param("owner") String owner,
            Pageable pageable
    );

    @Query("""
            SELECT t FROM Template t
            WHERE (t.sourceType IS NULL OR t.sourceType <> 'CUSTOM_PPTX')
              AND (:search IS NULL OR :search = ''
                OR LOWER(t.name) LIKE LOWER(CONCAT('%', :search, '%'))
                OR LOWER(t.description) LIKE LOWER(CONCAT('%', :search, '%')))
            """)
    Page<Template> searchPublicTemplates(@Param("search") String search, Pageable pageable);
}
