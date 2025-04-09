<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:output method="text" encoding="UTF-8"/>
  <xsl:template match="/">
    {
      "target": {
        "ip": "<xsl:value-of select="/nmaprun/host/address[@addrtype='ipv4']/@addr"/>",
        "port": "<xsl:value-of select="/nmaprun/host/ports/port/@portid"/>",
        "service": "<xsl:value-of select="/nmaprun/host/ports/port/service/@name"/>",
        "version": "<xsl:value-of select="concat(/nmaprun/host/ports/port/service/@product, ' ', /nmaprun/host/ports/port/service/@version, ' ', /nmaprun/host/ports/port/service/@extrainfo)"/>"
      },
      "tools": {
        "nikto": ["<xsl:value-of select="concat(/nmaprun/host/address[@addrtype='ipv4']/@addr, ' ', /nmaprun/host/ports/port/@portid)"/>"],
        "hydra": ["<xsl:value-of select="concat(/nmaprun/host/address[@addrtype='ipv4']/@addr, ' ', /nmaprun/host/ports/port/@portid, ' ', /nmaprun/host/ports/port/service/@name)"/>"],
        "metasploit": {
          "scripts": [<xsl:for-each select="/nmaprun/host/ports/port/script[@id != 'vulners']">"<xsl:value-of select="@id"/>"<xsl:if test="position() != last()">,</xsl:if></xsl:for-each>],
          "vulners": [<xsl:for-each select="/nmaprun/host/ports/port/script[@id='vulners']/table/table">
            {"id": "<xsl:value-of select="elem[@key='id']"/>",
             "type": "<xsl:value-of select="elem[@key='type']"/>",
             "cvss": "<xsl:value-of select="elem[@key='cvss']"/>",
             "exploit": <xsl:value-of select="elem[@key='is_exploit']"/>}<xsl:if test="position() != last()">,</xsl:if>
          </xsl:for-each>]
        }
      }
    }
  </xsl:template>
</xsl:stylesheet>