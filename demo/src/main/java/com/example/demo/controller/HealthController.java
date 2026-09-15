package com.example.demo.controller;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * Lightweight liveness check for uptime pingers (e.g. UptimeRobot, cron-job.org)
 * to keep the Render free-tier instance from spinning down. Deliberately does NOT
 * touch the database, so pinging it stays fast and free of any query load.
 * Publicly accessible: SecurityConfig's anyRequest().permitAll() catch-all covers
 * this path since it isn't one of the ADMIN-restricted /api/employees/** routes.
 */
@RestController
public class HealthController {

    @GetMapping("/health")
    public ResponseEntity<?> health() {
        return ResponseEntity.ok(Map.of("status", "ok"));
    }
}
