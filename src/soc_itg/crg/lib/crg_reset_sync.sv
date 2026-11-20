// -----------------------------------------------------------------------------
// crg_reset_sync : asynchronous assert / synchronous release reset synchronizer
//   rst_n_out follows rst_n_in low immediately; release is synchronized to
//   clk through a chain of STAGES crg_sync_cell wrappers (technology-replaceable).
// -----------------------------------------------------------------------------
`timescale 1ns/1ps
module crg_reset_sync #(
  parameter integer STAGES = 2
)(
  input  logic clk,
  input  logic rst_n_in,
  output logic rst_n_out
);
  initial begin
    if (STAGES < 2)
      $error("crg_reset_sync: STAGES must be >= 2 (got %0d)", STAGES);
  end

  logic [STAGES-1:0] sync_q;
  genvar i;
  generate
    for (i = 0; i < STAGES; i = i + 1) begin : g_sync
      crg_sync_cell u_cell (
        .clk  (clk),
        .d    (i == 0 ? 1'b1 : sync_q[i-1]),
        .rst_n(rst_n_in),
        .q    (sync_q[i])
      );
    end
  endgenerate

  assign rst_n_out = sync_q[STAGES-1];

`ifndef CRG_NO_CHECKS
  // portable checker: output released only while input released
  always @(posedge clk)
    if (rst_n_out && !rst_n_in)
      $display("CRG_CHECK_ERROR: crg_reset_sync rst_n_out high while rst_n_in low");
`endif
endmodule
