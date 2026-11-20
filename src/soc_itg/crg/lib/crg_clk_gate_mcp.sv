// -----------------------------------------------------------------------------
// crg_clk_gate_mcp : glitch-free clock gate for reset clock gating (MCP).
//   en comes from crg_rst_mcp, which runs on the same-frequency free clock
//   (quasi-static). Latch-based ICG without an enable synchronizer, so the
//   gate closes immediately when the sequencer leaves RUN.
// -----------------------------------------------------------------------------
`timescale 1ns/1ps
module crg_clk_gate_mcp (
  input  logic clk_in,
  input  logic en,
  output logic clk_out
);
  logic en_l;

  always_latch begin
    if (!clk_in) en_l = en;
  end

  assign clk_out = clk_in & en_l;

`ifndef CRG_NO_CHECKS
  // portable checker: no glitch (clk_out may only fall together with clk_in)
  always @(negedge clk_out)
    if (clk_in !== 1'b0)
      $display("CRG_CHECK_ERROR: crg_clk_gate_mcp glitch on clk_out");
`endif
endmodule