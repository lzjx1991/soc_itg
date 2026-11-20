// -----------------------------------------------------------------------------
// crg_rst_mcp : multi-cycle reset clock-enable sequencer (reset clock gating).
//   Runs on the FREE (ungated) domain clock and closes the domain clock gate
//   around both reset transitions, so no active clock edge occurs near a
//   reset assert or release -> no recovery/removal timing analysis needed.
//   Sequence: RUN --(async assert, gate closes)--> GUARD(2) --> PULSE
//   (PULSE_CYCLES clock cycles while reset is held asserted) --> WAIT (2FF
//   release) --> MARGIN(MARGIN_CYCLES) --> RUN (gate opens).
//   PULSE exits early when the synchronized reset releases (short asserts).
//   The FSM is asynchronously reset by rst_n_src, so the gate closes without
//   needing a clock edge.
// -----------------------------------------------------------------------------
`timescale 1ns/1ps
module crg_rst_mcp #(
  parameter integer MARGIN_CYCLES = 2,   // idle cycles after release
  parameter integer PULSE_CYCLES  = 128  // clock cycles during assert
)(
  input  logic clk_free,
  input  logic rst_n_src,   // async assert (low = asserted); resets the FSM
  input  logic rst_n_sync,  // 2FF-released reset (high = released)
  output logic clk_en
);
  initial begin
    if (MARGIN_CYCLES < 1)
      $error("crg_rst_mcp: MARGIN_CYCLES must be >= 1 (got %0d)",
             MARGIN_CYCLES);
    if (PULSE_CYCLES < 1)
      $error("crg_rst_mcp: PULSE_CYCLES must be >= 1 (got %0d)",
             PULSE_CYCLES);
    if (MARGIN_CYCLES > 255 || PULSE_CYCLES > 255)
      $error("crg_rst_mcp: counters are 8-bit (max 255)");
  end

  typedef enum logic [2:0] {S_GUARD = 3'd0, S_PULSE, S_WAIT, S_MARGIN,
                            S_RUN} st_e;
  st_e   state;
  logic [7:0] cnt;

  localparam logic [7:0] PULSE_LAST  = PULSE_CYCLES - 1;
  localparam logic [7:0] MARGIN_LAST = MARGIN_CYCLES - 1;

  always_ff @(posedge clk_free or negedge rst_n_src) begin
    if (!rst_n_src) begin
      state <= S_GUARD;
      cnt   <= 8'd0;
    end else begin
      case (state)
        S_GUARD: begin
          if (cnt == 8'd1) begin
            state <= S_PULSE;
            cnt   <= 8'd0;
          end else begin
            cnt <= cnt + 8'd1;
          end
        end
        S_PULSE: begin
          if (rst_n_sync) begin              // source released early
            state <= S_MARGIN;
            cnt   <= 8'd0;
          end else if (cnt == PULSE_LAST) begin
            state <= S_WAIT;
            cnt   <= 8'd0;
          end else begin
            cnt <= cnt + 8'd1;
          end
        end
        S_WAIT: begin
          if (rst_n_sync) begin
            state <= S_MARGIN;
            cnt   <= 8'd0;
          end
        end
        S_MARGIN: begin
          if (cnt == MARGIN_LAST) begin
            state <= S_RUN;
            cnt   <= 8'd0;
          end else begin
            cnt <= cnt + 8'd1;
          end
        end
        S_RUN: begin
          cnt <= 8'd0;   // hold; async assert returns to S_GUARD
        end
        default: begin
          state <= S_GUARD;
          cnt   <= 8'd0;   // X-safe entry (first edge after a late clock start)
        end
      endcase
    end
  end

  // gate enable: open only in RUN; during PULSE the clock runs while the
  // source is still asserted (reset level stable -> no recovery/removal)
  assign clk_en = (state == S_RUN) ||
                  ((state == S_PULSE) && !rst_n_src);

`ifndef CRG_NO_CHECKS
  // portable checker: no enable while waiting for release or in margin
  always @(posedge clk_free)
    if ((state == S_WAIT || state == S_MARGIN) && clk_en)
      $display("CRG_CHECK_ERROR: crg_rst_mcp clk_en while gated off");
`endif
endmodule