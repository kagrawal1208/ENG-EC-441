# Week 08 — Ethernet: Frame Structure, ARP, and Switch Self-Learning

This report analyzes Ethernet framing, ARP resolution, switching behavior, and subnet interactions based on Lecture 8. :contentReference[oaicite:1]{index=1}

---

# 1️⃣ Ethernet Frame Structure (Field-by-Field)

Ethernet frame format:

| Field | Size |
|-------|------|
| Preamble + SFD | 8 bytes |
| Destination MAC | 6 bytes |
| Source MAC | 6 bytes |
| Type | 2 bytes |
| Payload | 46–1500 bytes |
| FCS (CRC-32) | 4 bytes |

:contentReference[oaicite:2]{index=2}

### Field Purpose

### 🔹 Preamble (7 bytes)
Pattern 10101010 × 7  
Used for clock synchronization.

### 🔹 SFD (1 byte)
10101011  
Marks start of actual frame data.

### 🔹 Destination MAC (6 bytes)
48-bit hardware address of intended receiver.

### 🔹 Source MAC (6 bytes)
48-bit hardware address of sender.

### 🔹 Type (2 bytes)
Identifies encapsulated protocol:
- 0x0800 → IPv4
- 0x0806 → ARP
- 0x86DD → IPv6 :contentReference[oaicite:3]{index=3}

### 🔹 Payload (46–1500 bytes)
If payload < 46 bytes → padded to minimum.

### 🔹 FCS (4 bytes)
CRC-32 checksum. Frames with errors are silently dropped. :contentReference[oaicite:4]{index=4}

---

# 2️⃣ Minimum and Maximum Frame Size

### Maximum
Payload ≤ 1500 bytes  
Total frame = 1518 bytes :contentReference[oaicite:5]{index=5}  

This is why IP MTU = 1500 bytes.

---

### Minimum
Payload ≥ 46 bytes  
Total frame ≥ 64 bytes :contentReference[oaicite:6]{index=6}  

Why?

Because under CSMA/CD, the sender must still be transmitting when a collision echo returns.

Condition:

T ≥ 2τ  

Since T = L/R:

L ≥ 2τR :contentReference[oaicite:7]{index=7}  

For classic Ethernet:

- R = 10 Mb/s
- τ = 51.2 μs
- Lmin = 512 bits = 64 bytes :contentReference[oaicite:8]{index=8}  

✅ The 64-byte minimum frame size comes directly from physics.

Modern switched Ethernet is full-duplex, so collisions no longer occur — but the 64-byte minimum remains for backward compatibility.

---

# 3️⃣ MAC Address Structure

A MAC address is 48 bits:

Example:
A4:C3:F0:85:AC:2D :contentReference[oaicite:9]{index=9}  

### Structure

- First 3 bytes = OUI (manufacturer ID)
- Last 3 bytes = device-specific ID :contentReference[oaicite:10]{index=10}  

Special addresses:

- Broadcast: FF:FF:FF:FF:FF:FF
- Bit 0: unicast (0) / multicast (1)
- Bit 1: globally (0) / locally administered (1) :contentReference[oaicite:11]{index=11}  

MAC addresses are **flat**, unlike IP addresses (which are hierarchical).

---

# 4️⃣ ARP (Address Resolution Protocol)

Problem:
Host A wants to send to IP 192.168.1.20 but only knows the IP, not the MAC.

ARP resolves IP → MAC within a subnet. :contentReference[oaicite:12]{index=12}  

---

## ARP Exchange Example

Host A:
- IP: 192.168.1.10
- MAC: AA:AA:AA:AA:AA:AA

Host B:
- IP: 192.168.1.20
- MAC: BB:BB:BB:BB:BB:BB

### Step 1 — ARP Request (Broadcast)

Ethernet destination:
FF:FF:FF:FF:FF:FF  

Message:
"Who has 192.168.1.20? Tell me your MAC." :contentReference[oaicite:13]{index=13}  

All hosts on LAN receive it.

---

### Step 2 — ARP Reply (Unicast)

Host B replies:

Ethernet destination:
AA:AA:AA:AA:AA:AA  

Message:
"I am 192.168.1.20; my MAC is BB:BB:BB:BB:BB:BB." :contentReference[oaicite:14]{index=14}  

---

### Step 3 — Data Transmission

Host A sends frame:

Ethernet dst:
BB:BB:BB:BB:BB:BB  

ARP entry cached with TTL (~20 minutes). :contentReference[oaicite:15]{index=15}  

---

# 5️⃣ ARP for Off-Subnet Traffic

If Host A (192.168.1.10) wants to reach 10.20.30.5 (different subnet):

1. It checks subnet prefix
2. Sees destination is off-subnet
3. Consults routing table → default gateway
4. ARPs for router’s MAC
5. Sends frame to router’s MAC
6. Router forwards packet onward :contentReference[oaicite:16]{index=16}  

Important:

ARP operates only within a broadcast domain (subnet). :contentReference[oaicite:17]{index=17}  

---

# 6️⃣ Hub vs Switch

### Hub
- Repeats frames to all ports
- Single collision domain
- Half-duplex
- Uses CSMA/CD :contentReference[oaicite:18]{index=18}  

---

### Switch
- Forwards based on MAC table
- Each port = separate collision domain
- Full-duplex
- No collisions :contentReference[oaicite:19]{index=19}  

Switches replaced hubs because:
- Better performance
- Better privacy
- Full-duplex capability

---

# 7️⃣ Switch Self-Learning Algorithm

Switch maintains forwarding table:

| MAC | Port | TTL |
|-----|------|-----|

:contentReference[oaicite:20]{index=20}  

### When frame arrives:

1. Learn source MAC → ingress port
2. Lookup destination MAC
3. If known → forward to specific port
4. If unknown → flood all except ingress
5. Broadcast → flood :contentReference[oaicite:21]{index=21}  

Entries expire after ~300 seconds.

---

## Example Flow

A → B (table empty)

Switch:
- Learns A → port 1
- B unknown → floods

B replies:
- Learns B → port 2
- A known → forwards only to port 1

After learning:
No more flooding needed. :contentReference[oaicite:22]{index=22}  

---

# 8️⃣ Subnets

Definition:

A subnet is a group of interfaces sharing the same IP prefix and reachable without a router. :contentReference[oaicite:23]{index=23}  

Example:

192.168.1.0/24  

- First 24 bits = network prefix
- Last 8 bits = host identifier

ARP works within subnet only.

Cross-subnet communication requires routing. :contentReference[oaicite:24]{index=24}  

---

# Final Key Takeaways

- Ethernet frame format is consistent across generations
- 64-byte minimum frame size came from CSMA/CD physics
- MAC addresses are flat 48-bit identifiers
- ARP resolves IP → MAC via broadcast request + unicast reply
- Switches self-learn MAC → port mappings
- Subnets define broadcast domains
- Modern Ethernet is switched, full-duplex, collision-free :contentReference[oaicite:25]{index=25}
