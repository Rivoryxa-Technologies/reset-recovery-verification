// SPDX-License-Identifier: MIT
`timescale 1ns/1ps

module tb_reset_recovery;
`ifndef DATA_WIDTH
    localparam integer DATA_WIDTH = 8;
`else
    localparam integer DATA_WIDTH = `DATA_WIDTH;
`endif
`ifndef STAGES
    localparam integer STAGES = 3;
`else
    localparam integer STAGES = `STAGES;
`endif
`ifndef BIAS
    localparam integer BIAS = 7;
`else
    localparam integer BIAS = `BIAS;
`endif
`ifndef MUTANT
    localparam integer MUTANT = 0;
`else
    localparam integer MUTANT = `MUTANT;
`endif

    reg clk = 0;
    reg rst = 1;
    reg req_valid = 0;
    reg [DATA_WIDTH-1:0] req_data = 0;
    wire req_ready;
    wire rsp_valid;
    wire [DATA_WIDTH-1:0] rsp_data;

    reg [DATA_WIDTH-1:0] expected [0:4095];
    integer head = 0;
    integer tail = 0;
    integer errors = 0;
    integer accepted = 0;
    integer returned = 0;
    integer reset_count = 0;
    integer seed = 1;
    integer random_state;
    integer cycle;
    integer clock_count = 0;
    integer expected_cycle [0:4095];
    reg reset_check_active = 0;
    reg reset_sampled = 0;

    response_pipeline #(
        .DATA_WIDTH(DATA_WIDTH), .STAGES(STAGES), .BIAS(BIAS),
        .MUTANT_KEEP_VALID_ON_RESET(MUTANT)
    ) dut (
        .clk(clk), .rst(rst), .req_valid(req_valid), .req_ready(req_ready),
        .req_data(req_data), .rsp_valid(rsp_valid), .rsp_data(rsp_data)
    );

    always #5 clk = ~clk;

    task drive_request;
        input [DATA_WIDTH-1:0] value;
        begin
            @(negedge clk);
            req_valid = 1;
            req_data = value;
        end
    endtask

    task drive_idle;
        begin
            @(negedge clk);
            req_valid = 0;
            req_data = 0;
        end
    endtask

    task pulse_reset;
        input integer clocks;
        integer n;
        begin
            @(negedge clk);
            req_valid = 0;
            rst = 1;
            for (n = 0; n < clocks; n = n + 1)
                @(negedge clk);
            rst = 0;
        end
    endtask

    always @(posedge clk) begin
        clock_count = clock_count + 1;
        reset_sampled = rst;
        if (rst) begin
            // Requests accepted before reset are cancelled by contract.
            head = 0;
            tail = 0;
            reset_count = reset_count + 1;
        end else begin
            if (req_valid && req_ready) begin
                expected[tail] = req_data + BIAS;
                expected_cycle[tail] = clock_count + STAGES;
                tail = tail + 1;
                accepted = accepted + 1;
            end
            if (rsp_valid) begin
                if (head == tail) begin
                    $display("RESET_FLUSH_CHECK_FAILED: ghost response data=0x%0h after reset", rsp_data);
                    errors = errors + 1;
                end else begin
                    if (clock_count != expected_cycle[head]) begin
                        $display("LATENCY_CHECK_FAILED: expected_cycle=%0d actual_cycle=%0d", expected_cycle[head], clock_count);
                        errors = errors + 1;
                    end
                    if (rsp_data !== expected[head]) begin
                        $display("ORDERING_DATA_CHECK_FAILED: expected=0x%0h actual=0x%0h", expected[head], rsp_data);
                        errors = errors + 1;
                    end
                    head = head + 1;
                    returned = returned + 1;
                end
            end
        end
    end

    always @(negedge clk) begin
        if (reset_check_active && rst && reset_sampled && (rsp_valid !== 1'b0)) begin
            $display("RESET_FLUSH_CHECK_FAILED: rsp_valid=%b while reset is active", rsp_valid);
            errors = errors + 1;
        end
    end

    initial begin
        if (!$value$plusargs("SEED=%d", seed))
            seed = 1;
        random_state = seed;

        // Establish a clean reset, then reset with several requests pending.
        repeat (2) @(negedge clk);
        rst = 0;
        // Fill even the mutant's initially unknown valid state with known zeros.
        repeat (STAGES) @(negedge clk);
        reset_check_active = 1;
        drive_request(8'h11);
        drive_request(8'h22);
        drive_request(8'h33);
        pulse_reset(1);

        // Recovery must accept and return ordered data immediately afterward.
        drive_request(8'h41);
        drive_request(8'h42);
        drive_request(8'h43);
        drive_idle();
        repeat (STAGES + 2) @(negedge clk);

        // Repeated resets: empty, then pending, then empty again.
        pulse_reset(1);
        drive_request(8'h55);
        pulse_reset(2);
        pulse_reset(1);

        // Seeded mixed traffic and synchronous resets.
        for (cycle = 0; cycle < 80; cycle = cycle + 1) begin
            @(negedge clk);
            random_state = $random(random_state);
            if ((cycle == 17) || (cycle == 18) || ((random_state & 8'h3f) == 0)) begin
                rst = 1;
                req_valid = 0;
            end else begin
                rst = 0;
                req_valid = random_state[0];
                req_data = random_state[DATA_WIDTH-1:0];
            end
        end
        @(negedge clk);
        rst = 0;
        req_valid = 0;
        repeat (STAGES + 3) @(negedge clk);

        if (head != tail) begin
            $display("DRAIN_CHECK_FAILED: %0d expected responses remain", tail - head);
            errors = errors + 1;
        end
        if (errors == 0) begin
            $display("TEST_PASS: reset recovery verified seed=%0d width=%0d stages=%0d accepted=%0d returned=%0d resets=%0d", seed, DATA_WIDTH, STAGES, accepted, returned, reset_count);
            $finish(0);
        end
        $fatal(1, "TEST_FAIL: errors=%0d", errors);
    end

    initial begin
        #20000;
        $fatal(1, "TEST_TIMEOUT");
    end
endmodule
