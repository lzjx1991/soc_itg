// -----------------------------------------------------------------------------
// crg_clk_gate : software clock gate with internal 2FF synchronization
//   en comes from a CSR (pclk domain, quasi-static); it is synchronized into
//   the clk_in domain, then applied through a latch-based ICG (glitch-free).
//   rst_n must be a reset valid for the clk_in domain.
// -----------------------------------------------------------------------------
`timescale 1ns/1ps
module crg_clk_gate (
  input  logic clk_in,
  input  logic rst_n,
  input  logic en,
  output logic clk_out
);
  logic [1:0] en_sync;
  logic       en_l;

  always_ff @(posedge clk_in or negedge rst_n) begin
    if (!rst_n) begin
      en_sync[1] <= 1'b0;
      en_sync[0] <= 1'b0;
    end else begin
      en_sync[1] <= en_sync[0];
      en_sync[0] <= en;
    end
  end

  logic en_s1;
  assign en_s1 = en_sync[1];

  always_latch begin
    if (!clk_in) en_l = en_s1;
  end

  assign clk_out = clk_in & en_l;

`ifndef CRG_NO_CHECKS
  // portable checker: no glitch (clk_out may only fall together with clk_in)
  always @(negedge clk_out)
    if (clk_in !== 1'b0)
      $display("CRG_CHECK_ERROR: crg_clk_gate glitch on clk_out (clk_in high)");
`endif
endmodule
