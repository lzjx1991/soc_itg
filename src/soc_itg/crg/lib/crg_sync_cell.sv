// -----------------------------------------------------------------------------
// crg_sync_cell : single synchronizer flip-flop wrapper.
// Behavioral default for simulation; replace this module body (or map it) to
// the target technology library cell for synthesis -- all CDC/reset-synchron
// structures instantiate this wrapper only, so a library swap touches one file.
// -----------------------------------------------------------------------------
`timescale 1ns/1ps
module crg_sync_cell (
  input  logic clk,     // destination-domain clock
  input  logic d,       // asynchronous / source-domain data
  input  logic rst_n,   // asynchronous reset, active-low
  output logic q        // q = d delayed one destination cycle
);
  (* ASYNC_REG = "TRUE" *) logic q_r;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) q_r <= 1'b0;
    else        q_r <= d;
  end

  assign q = q_r;
endmodule
