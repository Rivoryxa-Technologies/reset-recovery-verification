// SPDX-License-Identifier: MIT
// A small, synthesizable request/response pipeline.
module response_pipeline #(
    parameter integer DATA_WIDTH = 8,
    parameter integer STAGES = 3,
    parameter integer BIAS = 1,
    // Teaching-only switch used to demonstrate the reset-validity defect.
    parameter integer MUTANT_KEEP_VALID_ON_RESET = 0
) (
    input  wire                  clk,
    input  wire                  rst,
    input  wire                  req_valid,
    output wire                  req_ready,
    input  wire [DATA_WIDTH-1:0] req_data,
    output wire                  rsp_valid,
    output wire [DATA_WIDTH-1:0] rsp_data
);
    reg [STAGES-1:0] valid_pipe;
    reg [DATA_WIDTH-1:0] data_pipe [0:STAGES-1];
    integer i;

    assign req_ready = ~rst;
    assign rsp_valid = valid_pipe[STAGES-1];
    assign rsp_data = data_pipe[STAGES-1];

    always @(posedge clk) begin
        if (rst) begin
            // The contract: a sampled reset cancels every in-flight request.
            if (!MUTANT_KEEP_VALID_ON_RESET)
                valid_pipe <= {STAGES{1'b0}};
            for (i = 0; i < STAGES; i = i + 1)
                data_pipe[i] <= {DATA_WIDTH{1'b0}};
        end else begin
            valid_pipe[0] <= req_valid && req_ready;
            data_pipe[0] <= req_data + BIAS;
            for (i = 1; i < STAGES; i = i + 1) begin
                valid_pipe[i] <= valid_pipe[i-1];
                data_pipe[i] <= data_pipe[i-1];
            end
        end
    end

    initial begin
        if (STAGES < 1) begin
            $display("CONFIGURATION_ERROR: STAGES must be at least 1");
            $finish(2);
        end
    end
endmodule
