package com.backend.userservice.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import com.backend.userservice.entity.UserEntity;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

@Repository
public interface UserRepository extends JpaRepository<UserEntity, UUID> {
     Optional<UserEntity> findByEmail(String email);
     boolean existsByEmail(String email);
     Optional<UserEntity> findByUsername(String name);
     Optional<UserEntity> findByGoogleId(String googleId);
}
