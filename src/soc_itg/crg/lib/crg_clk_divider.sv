// -----------------------------------------------------------------------------
// crg_clk_divider : integer clock divider with software-configurable ratio
//   ratio = 2..MAX_RATIO  : clk_out period = clk_in period * ratio
//                           high = (ratio-1)/2 + 1 cycles, low = remainder
//   ratio <= 1            : bypass, clk_out = clk_in (used for /1)
//   ratio is quasi-static SW control, sampled at posedge clk_in only.
//   Comparators use >= so a mid-flight ratio shrink recovers within one cycle.
//   en=0 freezes counter and output.
//   rst_n must be (or be synchronized to) a reset valid for the clk_in domain.
// -----------------------------------------------------------------------------
`timescale 1ns/1ps
module crg_clk_divider #(
  parameter integer MAX_RATIO = 2
)(
  input  logic                     clk_in,
  input  logic                     rst_n,
  input  logic                     en,
  input  logic [$clog2(MAX_RATIO):0] ratio,
  output logic                     clk_out
);
  initial begin
    if (MAX_RATIO < 2)
      $error("crg_clk_divider: MAX_RATIO must be >= 2 (got %0d)", MAX_RATIO);
  end

  logic [$clog2(MAX_RATIO):0] cnt;
  logic [$clog2(MAX_RATIO):0] ratio_m1, ratio_half;
  logic                       out_q;
  logic                       bypass;

  always_comb begin
    ratio_m1   = ratio - 1'b1;
    ratio_half = (ratio - 1'b1) >> 1;
    bypass     = (ratio <= 1'b1);
  end

  always_ff @(posedge clk_in or negedge rst_n) begin
    if (!rst_n) begin
      cnt   <= '0;
      out_q <= 1'b1;
    end else if (en) begin
      cnt <= (cnt >= ratio_m1) ? '0 : cnt + 1'b1;
      if (cnt >= ratio_m1)
        out_q <= 1'b1;
      else if (cnt >= ratio_half)
        out_q <= 1'b0;
    end
  end

  assign clk_out = bypass ? clk_in : out_q;

`ifndef CRG_NO_CHECKS
  // portable checker: output must not toggle while disabled
  logic out_d;
  always_ff @(posedge clk_in or negedge rst_n)
    if (!rst_n) out_d <= 1'b1;
    else        out_d <= clk_out;
  always @(posedge clk_in)
    if (rst_n && !en)
      assert (clk_out === out_d)
        else $display("CRG_CHECK_ERROR: crg_clk_divider clk_out toggled while en=0");
`endif
endmodule
