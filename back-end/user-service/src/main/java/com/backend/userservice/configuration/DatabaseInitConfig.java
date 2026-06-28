package com.backend.userservice.configuration;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeansException;
import org.springframework.beans.factory.config.BeanFactoryPostProcessor;
import org.springframework.beans.factory.config.ConfigurableListableBeanFactory;
import org.springframework.context.EnvironmentAware;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Component;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;

@Component
@Slf4j
public class DatabaseInitConfig implements BeanFactoryPostProcessor, EnvironmentAware {

    private Environment environment;

    @Override
    public void setEnvironment(Environment environment) {
        this.environment = environment;
    }

    @Override
    public void postProcessBeanFactory(ConfigurableListableBeanFactory beanFactory) throws BeansException {
        String url = environment.getProperty("spring.datasource.url");
        String username = environment.getProperty("spring.datasource.username");
        String password = environment.getProperty("spring.datasource.password");

        if (url == null || !url.startsWith("jdbc:postgresql:")) {
            return;
        }

        log.info("[user-service] Checking if PostgreSQL database exists for URL: {}", url);
        try {
            String cleanUrl = url;
            if (cleanUrl.contains("?")) {
                cleanUrl = cleanUrl.split("\\?")[0];
            }
            int lastSlash = cleanUrl.lastIndexOf('/');
            if (lastSlash == -1) {
                return;
            }
            String baseUri = cleanUrl.substring(0, lastSlash + 1) + "postgres";
            String dbName = cleanUrl.substring(lastSlash + 1);

            Class.forName("org.postgresql.Driver");
            try (Connection conn = DriverManager.getConnection(baseUri, username, password)) {
                try (Statement stmt = conn.createStatement()) {
                    boolean exists = false;
                    try (ResultSet rs = stmt.executeQuery("SELECT 1 FROM pg_database WHERE datname = '" + dbName + "'")) {
                        if (rs.next()) {
                            exists = true;
                        }
                    }
                    if (!exists) {
                        stmt.executeUpdate("CREATE DATABASE " + dbName);
                        log.info("[user-service] Created database: {}", dbName);
                    } else {
                        log.info("[user-service] Database {} already exists", dbName);
                    }
                }
            }
        } catch (ClassNotFoundException e) {
            log.error("[user-service] PostgreSQL driver not found", e);
        } catch (SQLException e) {
            log.error("[user-service] Failed to check or create database", e);
        }
    }
}
