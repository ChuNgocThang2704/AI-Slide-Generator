package com.backend.documentservice.repository;

import com.backend.documentservice.entity.SlidePage;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface SlidePageRepository extends JpaRepository<SlidePage, UUID> {
    List<SlidePage> findByProjectIdOrderByPageIndexAsc(UUID projectId);
}
