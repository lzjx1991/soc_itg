// -----------------------------------------------------------------------------
// crg_clk_mux2_glitchless : 2:1 glitch-free clock multiplexer
//   sel is quasi-static software control (CSR). On a sel change the currently
//   selected branch is disabled first; the new branch is enabled only after
//   the old branch's disable is observed (2FF synchronized) in the new domain.
//   During switching the output may be low for a few cycles (by design).
//   rst_n may be asynchronous to both clk0 and clk1 (assert only).
// -----------------------------------------------------------------------------
`timescale 1ns/1ps
module crg_clk_mux2_glitchless (
  input  logic clk0,
  input  logic clk1,
  input  logic rst_n,
  input  logic sel,
  output logic clk_out
);
  logic en0, en1;
  logic en0_off_meta, en0_off_sync; // "en0 == 0" observed in clk1 domain
  logic en1_off_meta, en1_off_sync; // "en1 == 0" observed in clk0 domain

  always_ff @(posedge clk0 or negedge rst_n)
    if (!rst_n) en0 <= 1'b0;
    else        en0 <= ~sel & en1_off_sync;

  always_ff @(posedge clk1 or negedge rst_n)
    if (!rst_n) en1 <= 1'b0;
    else        en1 <= sel & en0_off_sync;

  always_ff @(posedge clk0 or negedge rst_n)
    if (!rst_n) {en1_off_sync, en1_off_meta} <= 2'b00;
    else        {en1_off_sync, en1_off_meta} <= {en1_off_meta, ~en1};

  always_ff @(posedge clk1 or negedge rst_n)
    if (!rst_n) {en0_off_sync, en0_off_meta} <= 2'b00;
    else        {en0_off_sync, en0_off_meta} <= {en0_off_meta, ~en0};

  logic g0_l, g1_l;
  always_latch begin
    if (!clk0) g0_l = en0;
    if (!clk1) g1_l = en1;
  end

  assign clk_out = (clk0 & g0_l) | (clk1 & g1_l);

`ifndef CRG_NO_CHECKS
  // portable checker: both branches never enabled simultaneously
  always @(posedge clk0)
    if (en0 && en1)
      $display("CRG_CHECK_ERROR: crg_clk_mux2 en0 and en1 both active (clk0)");
  always @(posedge clk1)
    if (en0 && en1)
      $display("CRG_CHECK_ERROR: crg_clk_mux2 en0 and en1 both active (clk1)");
  // portable checker: output may only fall together with an input clock
  always @(negedge clk_out)
    if (clk0 !== 1'b0 && clk1 !== 1'b0)
      $display("CRG_CHECK_ERROR: crg_clk_mux2 glitch on clk_out (both inputs high)");
`endif
endmodule
