package com.backend.documentservice.repository;

import com.backend.documentservice.entity.ScriptSet;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface ScriptSetRepository extends JpaRepository<ScriptSet, UUID> {

    /** A row of the list: everything but the scripts themselves, which can be megabytes. */
    interface Summary {
        UUID getId();
        String getName();
        Integer getItemCount();
        Integer getTotalWords();
        Integer getTotalMinutes();
        Instant getCreatedAt();
        Instant getUpdatedAt();
    }

    @Query("select s.id as id, s.name as name, s.itemCount as itemCount, s.totalWords as totalWords, "
            + "s.totalMinutes as totalMinutes, s.createdAt as createdAt, s.updatedAt as updatedAt "
            + "from ScriptSet s where s.userId = :userId order by s.updatedAt desc")
    List<Summary> findSummariesByUserId(@Param("userId") UUID userId);

    Optional<ScriptSet> findByIdAndUserId(UUID id, UUID userId);

    long countByUserId(UUID userId);
}
