function auto_blackbox_report(csvPath, reportJsonPath)
%AUTO_BLACKBOX_REPORT Plot a blackbox CSV and optional Python JSON report.
%
% Usage from MATLAB:
%   auto_blackbox_report('blackbox_logs/blackbox_20260419_163409.csv')
%   auto_blackbox_report('blackbox_logs/xxx.csv', 'analysis_reports/xxx_report.json')

if nargin < 1 || strlength(string(csvPath)) == 0
    [file, path] = uigetfile('*.csv', '选择黑匣子 CSV');
    if isequal(file, 0)
        disp('未选择文件');
        return;
    end
    csvPath = fullfile(path, file);
end

if nargin < 2
    reportJsonPath = "";
end

T = readtable(csvPath, 'VariableNamingRule', 'preserve');
if ~ismember('packet_timestamp', T.Properties.VariableNames)
    error('CSV 缺少 packet_timestamp 列');
end

timeAxis = double(T.packet_timestamp);
timeAxis = timeAxis - timeAxis(1);
if max(timeAxis) > 1000
    timeAxis = timeAxis / 1000;
end

fig = figure('Color', 'w', 'Name', ['Blackbox 自动分析: ', char(csvPath)], ...
    'Position', [80 80 1400 900]);
tiledlayout(fig, 4, 1, 'TileSpacing', 'compact');

nexttile;
plot(timeAxis, [T.angle_roll, T.angle_pitch, T.angle_yaw], 'LineWidth', 1.1);
grid on; ylabel('Angle'); legend('roll', 'pitch', 'yaw');
title('姿态角');

nexttile;
plot(timeAxis, [T.gyro_x, T.gyro_y, T.gyro_z], 'LineWidth', 1.1);
grid on; ylabel('Gyro'); legend('x', 'y', 'z');
title('角速度');

nexttile;
plot(timeAxis, [T.acc_x, T.acc_y, T.acc_z], 'LineWidth', 1.1);
grid on; ylabel('Acc'); legend('x', 'y', 'z');
title('加速度');

nexttile;
plot(timeAxis, [T.rudder1, T.rudder2, T.rudder3, T.rudder4], 'LineWidth', 1.1);
grid on; ylabel('Rudder'); xlabel('time / s'); legend('r1', 'r2', 'r3', 'r4');
title('舵面输出');

if strlength(string(reportJsonPath)) > 0 && isfile(reportJsonPath)
    raw = fileread(reportJsonPath);
    report = jsondecode(raw);
    fprintf('\n=== Python 分析摘要 ===\n');
    fprintf('Rows: %d\n', report.summary.row_count);
    fprintf('Sample rate: %.2f Hz\n', report.summary.sample_rate_hz);
    fprintf('Duration: %.2f s\n', report.summary.duration_s);

    corrFig = figure('Color', 'w', 'Name', '相关性摘要', 'Position', [180 120 900 420]);
    names = fieldnames(report.correlations);
    values = zeros(numel(names), 1);
    for i = 1:numel(names)
        values(i) = report.correlations.(names{i}).zero_lag;
    end
    bar(categorical(names), values);
    ylim([-1, 1]); grid on;
    title('舵面组合与角速度零延迟相关系数');
    ylabel('correlation');
end
end
