from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.packet import arp, ethernet

log = core.getLogger()

arp_table = {}

# INSTALL FLOW RULE WHEN SWITCH CONNECTS
def _handle_ConnectionUp(event):
    log.info("Switch connected!")

    def install_flow():
        log.info("Installing flow rule now")

        fm = of.ofp_flow_mod()

        # Match IPv4 traffic
        fm.match = of.ofp_match()
        fm.match.dl_type = 0x0800
        fm.match.nw_src = "10.0.0.1"
        fm.match.nw_dst = "10.0.0.3"

        fm.priority = 65535
        fm.idle_timeout = 300
        fm.hard_timeout = 600

        # DROP action
        fm.actions = []

        event.connection.send(fm)

    core.callDelayed(2, install_flow)


# HANDLE PACKETS (ARP + FORWARDING)
def _handle_PacketIn(event):
    packet = event.parsed

    if not packet.parsed:
        return

    # ARP HANDLING
    if packet.type == ethernet.ARP_TYPE:
        arp_pkt = packet.payload

        log.info("ARP: %s -> %s", arp_pkt.protosrc, arp_pkt.protodst)

        arp_table[arp_pkt.protosrc] = packet.src

        # BLOCK ARP h1 → h3
        if str(arp_pkt.protosrc) == "10.0.0.1" and str(arp_pkt.protodst) == "10.0.0.3":
            log.info("Blocked ARP from h1 to h3")
            return

        # Reply if known
        if arp_pkt.protodst in arp_table:
            reply = arp()
            reply.hwsrc = arp_table[arp_pkt.protodst]
            reply.hwdst = packet.src
            reply.opcode = arp.REPLY
            reply.protosrc = arp_pkt.protodst
            reply.protodst = arp_pkt.protosrc

            ether = ethernet()
            ether.type = ethernet.ARP_TYPE
            ether.src = reply.hwsrc
            ether.dst = reply.hwdst
            ether.payload = reply

            msg = of.ofp_packet_out()
            msg.data = ether.pack()
            msg.actions.append(of.ofp_action_output(port=event.port))
            event.connection.send(msg)
            return

    # NORMAL FORWARDING
    msg = of.ofp_packet_out()
    msg.data = event.ofp
    msg.actions.append(of.ofp_action_output(port=of.OFPP_FLOOD))
    event.connection.send(msg)


# START CONTROLLER
def launch():
    core.openflow.addListenerByName("PacketIn", _handle_PacketIn)
    core.openflow.addListenerByName("ConnectionUp", _handle_ConnectionUp)
    log.info("ARP Controller Started")