package com.sangam.app.ui.screens

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.ArrowDropUp
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Dns
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.google.android.gms.auth.api.signin.GoogleSignIn
import com.google.android.gms.auth.api.signin.GoogleSignInOptions
import com.google.android.gms.common.api.ApiException
import com.google.firebase.firestore.FieldValue
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.firestore.SetOptions
import com.sangam.app.R
import com.sangam.app.network.ApiClient
import com.sangam.app.network.LoginRequest
import com.sangam.app.network.RealtimeClient
import com.sangam.app.network.RegisterRequest
import com.sangam.app.network.TokenManager
import kotlinx.coroutines.launch

@Composable
fun LoginScreen(onLoginSuccess: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val scrollState = rememberScrollState()

    var isLogin by remember { mutableStateOf(true) }
    var name by remember { mutableStateOf("") }
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var isPasswordFocused by remember { mutableStateOf(false) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    // Server Configuration State
    var showServerConfig by remember { mutableStateOf(false) }
    var serverUrlInput by remember { mutableStateOf(TokenManager.getServerUrl()) }
    var serverConfigSaved by remember { mutableStateOf(false) }

    // Google Sign-In Client
    val googleSignInClient = remember {
        val gso = GoogleSignInOptions.Builder(GoogleSignInOptions.DEFAULT_SIGN_IN)
            .requestEmail()
            .requestProfile()
            .build()
        GoogleSignIn.getClient(context, gso)
    }

    // Google Sign-In Activity Result Launcher
    val googleLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.StartActivityForResult()
    ) { result ->
        val task = GoogleSignIn.getSignedInAccountFromIntent(result.data)
        try {
            val account = task.getResult(ApiException::class.java)
            if (account != null) {
                scope.launch {
                    loading = true
                    error = null
                    try {
                        val uid = account.id ?: ("google_" + (account.email?.hashCode() ?: System.currentTimeMillis()))
                        val accountName = account.displayName ?: account.givenName ?: "Google User"
                        val accountEmail = account.email ?: ""

                        // 1. Cloud Database Sync (Firestore)
                        try {
                            val db = FirebaseFirestore.getInstance()
                            val userDoc = hashMapOf(
                                "uid" to uid,
                                "email" to accountEmail,
                                "name" to accountName,
                                "photoUrl" to (account.photoUrl?.toString() ?: ""),
                                "authProvider" to "google",
                                "lastLogin" to FieldValue.serverTimestamp()
                            )
                            db.collection("users").document(uid).set(userDoc, SetOptions.merge())
                        } catch (_: Exception) {
                            // Non-fatal if offline or firestore rules check in progress
                        }

                        // 2. Synchronize with backend API if accessible
                        var token = account.idToken ?: ("token_google_" + uid)
                        try {
                            val resp = ApiClient.authApi.login(
                                LoginRequest(email = accountEmail, password = "google_auth_$uid")
                            )
                            token = resp.access_token
                        } catch (_: Exception) {
                            try {
                                val regResp = ApiClient.authApi.register(
                                    RegisterRequest(name = accountName, email = accountEmail, password = "google_auth_$uid")
                                )
                                token = regResp.access_token
                            } catch (_: Exception) {
                                // Backend not currently reachable; use Google / Cloud identity token
                            }
                        }

                        // 3. Persist session
                        TokenManager.saveToken(token, uid, accountName, accountEmail)
                        try {
                            RealtimeClient.start()
                        } catch (_: Exception) {}

                        onLoginSuccess()
                    } catch (e: Exception) {
                        error = "Google Sign-In failed: ${e.message}"
                    } finally {
                        loading = false
                    }
                }
            }
        } catch (e: ApiException) {
            error = "Google Sign-In status ${e.statusCode}: ${e.message ?: "Sign-in was cancelled"}"
        } catch (e: Exception) {
            error = "Google Sign-In failed: ${e.message}"
        }
    }

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background,
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(scrollState)
                .padding(horizontal = 24.dp, vertical = 32.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            Spacer(modifier = Modifier.height(8.dp))

            Text(
                "Sangam",
                style = MaterialTheme.typography.displayMedium,
                color = MaterialTheme.colorScheme.primary,
                fontWeight = FontWeight.Bold,
            )
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                "AI-Native Voice Calling Platform",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(modifier = Modifier.height(14.dp))

            // Witty Duolingo-style Mascot Speech Bubble (White Theme)
            Surface(
                shape = RoundedCornerShape(16.dp),
                color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f),
                border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.4f)),
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 8.dp)
            ) {
                Text(
                    text = if (isPasswordFocused) {
                        "Psst! Enter your password. I've got my wings over my eyes, totally not peeking!"
                    } else {
                        "Namaste, ${if (name.isNotBlank()) name else "Varshini"}! Ready to deploy your Sarvam AI calling agents?"
                    },
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.Medium,
                    color = MaterialTheme.colorScheme.onSurface,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp)
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            // 100% Transparent Mascot (No background box!)
            Image(
                painter = painterResource(
                    id = if (isPasswordFocused) R.drawable.mascot_kite_peekaboo else R.drawable.mascot_kite_idle
                ),
                contentDescription = "Kite Master Mascot",
                modifier = Modifier
                    .size(130.dp)
                    .padding(bottom = 4.dp),
                contentScale = ContentScale.Fit
            )

            Spacer(modifier = Modifier.height(16.dp))

            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
            ) {
                Column(modifier = Modifier.padding(20.dp)) {

                    // Google Sign-In Button
                    OutlinedButton(
                        onClick = {
                            error = null
                            googleLauncher.launch(googleSignInClient.signInIntent)
                        },
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(50.dp),
                        enabled = !loading,
                        colors = ButtonDefaults.outlinedButtonColors(
                            containerColor = MaterialTheme.colorScheme.surface,
                            contentColor = MaterialTheme.colorScheme.onSurface,
                        ),
                    ) {
                        Image(
                            painter = painterResource(id = R.drawable.ic_google_logo),
                            contentDescription = "Google Logo",
                            modifier = Modifier.size(22.dp),
                        )
                        Spacer(modifier = Modifier.width(12.dp))
                        Text(
                            "Continue with Google",
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.SemiBold,
                        )
                    }

                    Spacer(modifier = Modifier.height(20.dp))

                    // Divider with "OR"
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        HorizontalDivider(modifier = Modifier.weight(1f))
                        Text(
                            "  or  ",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.outline,
                        )
                        HorizontalDivider(modifier = Modifier.weight(1f))
                    }

                    Spacer(modifier = Modifier.height(20.dp))

                    // Login / Register Selector
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.Center,
                    ) {
                        FilterChip(
                            selected = isLogin,
                            onClick = { isLogin = true; error = null },
                            label = { Text("Login") },
                        )
                        Spacer(modifier = Modifier.width(12.dp))
                        FilterChip(
                            selected = !isLogin,
                            onClick = { isLogin = false; error = null },
                            label = { Text("Register") },
                        )
                    }
                    Spacer(modifier = Modifier.height(16.dp))

                    if (!isLogin) {
                        OutlinedTextField(
                            value = name,
                            onValueChange = { name = it },
                            label = { Text("Name") },
                            modifier = Modifier.fillMaxWidth(),
                            singleLine = true,
                            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next),
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                    }

                    OutlinedTextField(
                        value = email,
                        onValueChange = { email = it },
                        label = { Text("Email") },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(
                            keyboardType = KeyboardType.Email,
                            imeAction = ImeAction.Next,
                        ),
                    )
                    Spacer(modifier = Modifier.height(12.dp))

                    OutlinedTextField(
                        value = password,
                        onValueChange = { password = it },
                        label = { Text("Password") },
                        modifier = Modifier
                            .fillMaxWidth()
                            .onFocusChanged { isPasswordFocused = it.isFocused },
                        singleLine = true,
                        visualTransformation = PasswordVisualTransformation(),
                        keyboardOptions = KeyboardOptions(
                            keyboardType = KeyboardType.Password,
                            imeAction = ImeAction.Done,
                        ),
                    )

                    if (error != null) {
                        Spacer(modifier = Modifier.height(12.dp))
                        Text(
                            error!!,
                            color = MaterialTheme.colorScheme.error,
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }

                    Spacer(modifier = Modifier.height(20.dp))

                    Button(
                        onClick = {
                            scope.launch {
                                loading = true
                                error = null
                                try {
                                    val trimmedEmail = email.trim()
                                    val trimmedName = name.trim()
                                    val resp = if (isLogin) {
                                        ApiClient.authApi.login(LoginRequest(trimmedEmail, password))
                                    } else {
                                        ApiClient.authApi.register(RegisterRequest(trimmedName, trimmedEmail, password))
                                    }

                                    // Cloud Firestore backup sync
                                    try {
                                        val db = FirebaseFirestore.getInstance()
                                        val docId = trimmedEmail.replace(".", "_")
                                        val userDoc = hashMapOf(
                                            "uid" to resp.actor_id,
                                            "email" to trimmedEmail,
                                            "name" to resp.name,
                                            "authProvider" to "email_password",
                                            "lastLogin" to FieldValue.serverTimestamp()
                                        )
                                        db.collection("users").document(docId).set(userDoc, SetOptions.merge())
                                    } catch (_: Exception) {}

                                    TokenManager.saveToken(resp.access_token, resp.actor_id, resp.name, trimmedEmail)
                                    try {
                                        RealtimeClient.start()
                                    } catch (_: Exception) {}

                                    onLoginSuccess()
                                } catch (e: Exception) {
                                    val rawMsg = e.message ?: "Authentication failed"
                                    error = if (rawMsg.contains("10.0.2.2") || rawMsg.contains("CLEARTEXT") || rawMsg.contains("failed to connect")) {
                                        "Could not reach backend at ${TokenManager.getServerUrl()}. If testing on a physical phone, expand 'Server Connection Settings' below to set your PC LAN IP, or use Google Sign-In."
                                    } else {
                                        rawMsg
                                    }
                                } finally {
                                    loading = false
                                }
                            }
                        },
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(48.dp),
                        enabled = !loading && email.isNotBlank() && password.isNotBlank() && (isLogin || name.isNotBlank()),
                    ) {
                        if (loading) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(20.dp),
                                color = MaterialTheme.colorScheme.onPrimary,
                                strokeWidth = 2.dp,
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                        }
                        Text(if (isLogin) "Sign In" else "Create Account")
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Expandable Server Connection Configuration
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)),
            ) {
                Column(modifier = Modifier.padding(12.dp)) {
                    TextButton(
                        onClick = { showServerConfig = !showServerConfig },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Icon(Icons.Default.Dns, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            "Server Connection Settings",
                            style = MaterialTheme.typography.labelLarge,
                        )
                        Spacer(modifier = Modifier.weight(1f))
                        Icon(
                            imageVector = if (showServerConfig) Icons.Default.ArrowDropUp else Icons.Default.ArrowDropDown,
                            contentDescription = null,
                        )
                    }

                    AnimatedVisibility(visible = showServerConfig) {
                        Column(modifier = Modifier.padding(top = 8.dp)) {
                            Text(
                                "Target Backend URL:",
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Spacer(modifier = Modifier.height(4.dp))
                            OutlinedTextField(
                                value = serverUrlInput,
                                onValueChange = {
                                    serverUrlInput = it
                                    serverConfigSaved = false
                                },
                                modifier = Modifier.fillMaxWidth(),
                                singleLine = true,
                                placeholder = { Text("http://192.168.1.x:8000") },
                            )
                            Spacer(modifier = Modifier.height(8.dp))
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Button(
                                    onClick = {
                                        TokenManager.saveServerUrl(serverUrlInput)
                                        serverConfigSaved = true
                                    },
                                    modifier = Modifier.height(36.dp),
                                ) {
                                    Icon(Icons.Default.Check, contentDescription = null, modifier = Modifier.size(16.dp))
                                    Spacer(modifier = Modifier.width(4.dp))
                                    Text("Apply URL", style = MaterialTheme.typography.labelMedium)
                                }
                                if (serverConfigSaved) {
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Text(
                                        "Saved!",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.primary,
                                    )
                                }
                            }
                            Spacer(modifier = Modifier.height(6.dp))
                            Text(
                                "Note: On physical Android devices, 10.0.2.2 is not reachable. Use your computer's Wi-Fi IP (e.g. http://192.168.1.5:8000) or tunnel URL. Google Sign-In works directly over Cloud.",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.outline,
                            )
                        }
                    }
                }
            }
        }
    }
}
