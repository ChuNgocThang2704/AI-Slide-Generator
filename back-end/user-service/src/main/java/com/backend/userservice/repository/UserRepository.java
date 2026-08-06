package com.backend.userservice.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import com.backend.userservice.entity.UserEntity;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface UserRepository extends JpaRepository<UserEntity, UUID> {
     Optional<UserEntity> findByEmail(String email);
     boolean existsByEmail(String email);
     Optional<UserEntity> findByUsername(String name);
     Optional<UserEntity> findByGoogleId(String googleId);

     @Query("SELECT COUNT(u) FROM users u WHERE u.createdAt < :date")
     long countUsersBefore(@Param("date") Instant date);

     @Query("SELECT COUNT(u) FROM users u WHERE u.createdAt >= :startDate AND u.createdAt <= :endDate")
     long countUsersBetween(@Param("startDate") Instant startDate, @Param("endDate") Instant endDate);

     long countByEmailVerifiedFalse();
}
