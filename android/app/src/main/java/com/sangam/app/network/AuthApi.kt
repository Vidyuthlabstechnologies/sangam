package com.sangam.app.network

import retrofit2.http.GET

data class MeResponse(
    val actor_id: String,
    val name: String,
    val email: String?,
    val organization_id: String?,
    val roles: List<String>,
)

interface AuthApi {
    @GET("/auth/me")
    suspend fun me(): MeResponse
}
