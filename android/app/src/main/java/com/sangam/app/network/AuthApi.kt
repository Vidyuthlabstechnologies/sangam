package com.sangam.app.network

import retrofit2.http.Body
import retrofit2.http.POST

data class LoginRequest(val email: String, val password: String)
data class RegisterRequest(val name: String, val email: String, val password: String, val type: String = "human")
data class TokenResponse(
    val access_token: String,
    val token_type: String,
    val expires_in: Int,
    val actor_id: String,
    val name: String,
    val roles: List<String>,
)

interface AuthApi {
    @POST("/auth/register")
    suspend fun register(@Body request: RegisterRequest): TokenResponse

    @POST("/auth/login")
    suspend fun login(@Body request: LoginRequest): TokenResponse
}
