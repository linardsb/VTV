"""XML namespace constants for NeTEx and SIRI documents."""

# NeTEx namespace (used in PublicationDelivery and all frames)
NETEX_NS = "http://www.netex.org.uk/netex"

# SIRI namespace (used in ServiceDelivery)
SIRI_NS = "http://www.siri.org.uk/siri"

# GML namespace (used for geographic elements in NeTEx)
GML_NS = "http://www.opengis.net/gml/3.2"

# XSI namespace (for schema instance attributes)
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

# Namespace maps for lxml element creation
NETEX_NSMAP: dict[str | None, str] = {
    None: NETEX_NS,
    "gml": GML_NS,
    "xsi": XSI_NS,
}

SIRI_NSMAP: dict[str | None, str] = {
    None: SIRI_NS,
}
