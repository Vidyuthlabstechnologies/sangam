package com.sangam.app.ui.screens

import com.sangam.app.R
import com.sangam.app.ui.components.str

import com.sangam.app.ui.components.ErrorState
import com.sangam.app.ui.components.friendlyError
import com.sangam.app.ui.components.BackButton
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.sangam.app.network.ApiClient
import com.sangam.app.network.VendorDto

/** Colour a vendor's status chip by how much attention it needs. */
@Composable
private fun statusColor(status: String): Color2 = when (status) {
    "qualified" -> Color2(MaterialTheme.colorScheme.primaryContainer, MaterialTheme.colorScheme.onPrimaryContainer)
    "pending_qualification" -> Color2(MaterialTheme.colorScheme.tertiaryContainer, MaterialTheme.colorScheme.onTertiaryContainer)
    "rejected", "suspended" -> Color2(MaterialTheme.colorScheme.errorContainer, MaterialTheme.colorScheme.onErrorContainer)
    else -> Color2(MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.colorScheme.onSurfaceVariant)
}

data class Color2(val bg: androidx.compose.ui.graphics.Color, val fg: androidx.compose.ui.graphics.Color)

private fun prettyStatus(s: String) = s.replace('_', ' ').replaceFirstChar { it.uppercase() }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VendorListScreen(
    onVendorClick: (String) -> Unit,
    onAddVendor: () -> Unit,
    onBack: () -> Unit = {},
) {
    var vendors by remember { mutableStateOf<List<VendorDto>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        try {
            vendors = ApiClient.api.listVendors()
        } catch (e: Exception) {
            error = friendlyError(e, str(R.string.load_vendors))
        }
        loading = false
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(str(R.string.vendors)) },
                navigationIcon = { BackButton(onBack) },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface
                ),
            )
        },
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = onAddVendor,
                icon = { Icon(Icons.Default.Add, contentDescription = null) },
                text = { Text(str(R.string.add_vendor)) },
            )
        },
    ) { padding ->
        when {
            loading -> Box(
                Modifier.fillMaxSize().padding(padding),
                contentAlignment = Alignment.Center,
            ) { CircularProgressIndicator() }

            error != null -> Box(
                Modifier.fillMaxSize().padding(padding).padding(24.dp),
                contentAlignment = Alignment.Center,
            ) { ErrorState(error!!, onRetry = null) }

            vendors.isEmpty() -> Box(
                Modifier.fillMaxSize().padding(padding).padding(24.dp),
                contentAlignment = Alignment.Center,
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(str(R.string.no_vendors_yet), style = MaterialTheme.typography.titleMedium)
                    Spacer(Modifier.height(8.dp))
                    Text(
                        str(R.string.add_a_supplier_and_photograph_their),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            else -> LazyColumn(
                modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                items(vendors) { v ->
                    VendorCard(v, onClick = { onVendorClick(v.id) })
                }
            }
        }
    }
}

@Composable
private fun VendorCard(vendor: VendorDto, onClick: () -> Unit) {
    // Surface the soonest expiry: a lapsed CDSCO licence halts production,
    // so it is the single most important thing on this row.
    val soonest = vendor.licences.mapNotNull { it.days_until_expiry }.minOrNull()
    val colors = statusColor(vendor.status)

    Card(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = CardDefaults.outlinedCardBorder(),
    ) {
        Column(Modifier.fillMaxWidth().padding(16.dp)) {
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.Top,
            ) {
                Column(Modifier.weight(1f)) {
                    Text(
                        vendor.name,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        vendor.gstin ?: str(R.string.gstin_not_on_file),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Surface(
                    color = colors.bg,
                    shape = MaterialTheme.shapes.small,
                ) {
                    Text(
                        prettyStatus(vendor.status),
                        color = colors.fg,
                        style = MaterialTheme.typography.labelMedium,
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                    )
                }
            }

            Spacer(Modifier.height(10.dp))
            Text(
                when (vendor.licences.size) {
                    0 -> str(R.string.no_licences_on_file_2)
                    1 -> str(R.string.n_1_licence_on_file)
                    else -> str(R.string.licences_on_file, vendor.licences.size)
                },
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            if (vendor.has_expired_licence) {
                Spacer(Modifier.height(6.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        Icons.Default.Warning,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.error,
                        modifier = Modifier.size(16.dp),
                    )
                    Spacer(Modifier.width(6.dp))
                    Text(
                        str(R.string.licence_expired_cannot_supply),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                        fontWeight = FontWeight.Medium,
                    )
                }
            } else if (soonest != null && soonest <= 90) {
                Spacer(Modifier.height(6.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        Icons.Default.Warning,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.tertiary,
                        modifier = Modifier.size(16.dp),
                    )
                    Spacer(Modifier.width(6.dp))
                    Text(
                        str(R.string.licence_expires_in_days, soonest),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.tertiary,
                        fontWeight = FontWeight.Medium,
                    )
                }
            }
        }
    }
}
