package com.backend.documentservice.repository;

import com.backend.documentservice.entity.Project;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

@Repository
public interface ProjectRepository extends JpaRepository<Project, UUID> {
    Page<Project> findByOwnerIdAndNameContainingIgnoreCase(UUID ownerId, String name, Pageable pageable);
    Page<Project> findByOwnerId(UUID ownerId, Pageable pageable);

    @Query("SELECT COUNT(p) FROM Project p WHERE p.createdAt < :date")
    long countProjectsBefore(@Param("date") Instant date);

    @Query("SELECT COUNT(p) FROM Project p WHERE p.createdAt >= :startDate AND p.createdAt <= :endDate")
    long countProjectsBetween(@Param("startDate") Instant startDate, @Param("endDate") Instant endDate);

    @Query("SELECT p.ownerId, COUNT(p) as cnt FROM Project p GROUP BY p.ownerId ORDER BY cnt DESC")
    List<Object[]> findTopActiveUsers(Pageable pageable);

    @Query("SELECT MONTH(p.createdAt) as m, COUNT(p) FROM Project p WHERE YEAR(p.createdAt) = :year AND p.createdAt >= :startDate AND p.createdAt <= :endDate GROUP BY m")
    List<Object[]> countProjectsByMonth(@Param("year") int year, @Param("startDate") Instant startDate, @Param("endDate") Instant endDate);

    @Query("SELECT COUNT(DISTINCT p.ownerId) FROM Project p")
    long countDistinctOwners();

    long countByOwnerIdAndCreatedAtBefore(UUID ownerId, Instant date);
    long countByOwnerIdAndCreatedAtBetween(UUID ownerId, Instant startDate, Instant endDate);

    @Query("SELECT p.ownerId, COUNT(p) FROM Project p WHERE p.ownerId IN :userIds AND p.createdAt < :date GROUP BY p.ownerId")
    List<Object[]> countProjectsBeforeForUsers(@Param("userIds") List<UUID> userIds, @Param("date") Instant date);

    @Query("SELECT p.ownerId, COUNT(p) FROM Project p WHERE p.ownerId IN :userIds AND p.createdAt >= :startDate AND p.createdAt <= :endDate GROUP BY p.ownerId")
    List<Object[]> countProjectsBetweenForUsers(@Param("userIds") List<UUID> userIds, @Param("startDate") Instant startDate, @Param("endDate") Instant endDate);

    @Query(value = "SELECT CAST(created_at AS DATE) as d, COUNT(id) FROM projects WHERE created_at >= :startDate AND created_at <= :endDate GROUP BY d ORDER BY d ASC", nativeQuery = true)
    List<Object[]> countProjectsByDay(@Param("startDate") Instant startDate, @Param("endDate") Instant endDate);
}
