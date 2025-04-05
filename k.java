//import java.io.BufferedReader;
//import java.io.FileReader;
//import java.io.IOException;
//import java.nio.file.Files;
//import java.nio.file.Path;
//import java.util.ArrayList;
//import java.util.List;
//import java.util.stream.Collectors;
//
//public class k {
//    public static void main(String[] args) throws IOException {
//        String filePath = "E:\\javatexts\\chinese-gushiwen\\writer\\111";
//        String output = "E:\\javatexts\\chinese-gushiwen\\writer\\111.json";
//        Files.createFile(Path.of(output));
//
//        try {
//            var w = Files.newBufferedWriter(Path.of(output));
//            w.write("[");
//            Files.list(Path.of(filePath)).forEach(path -> {
//                try {
//                    Files.lines(path).forEach(line -> {
//                        if (!line.endsWith(",")) {
//                            line = line + ",";
//                            try {
//                                w.write(line);
//                                w.flush();
//                            } catch (IOException e) {
//                                throw new RuntimeException(e);
//                            }
//                        }
//                    });
//                } catch (IOException e) {
//                    throw new RuntimeException(e);
//                }
//            });
//            w.write("\b]");
//            w.close();
//            System.out.println("ok");
//
////            System.out.println(arr);
////            // 读取文件内容
////            StringBuilder rawData = new StringBuilder();
////            BufferedReader reader = new BufferedReader(new FileReader(filePath));
////            String line;
////            int j=0;
////            while (j<10) {
////                line = reader.readLine();
////                rawData.append(line);
////                j++;
////            }
////            reader.close();
////
////            // 分割JSON对象
////            List<String> jsonObjects = splitJson(rawData.toString());
////
////            // 构建合法的JSON数组
////            StringBuilder jsonArray = new StringBuilder("[");
////            for (int i = 0; i < jsonObjects.size(); i++) {
////                if (i > 0) {
////                    jsonArray.append(",");
////                }
////                jsonArray.append(jsonObjects.get(i));
////            }
////            jsonArray.append("]");
////
////            // 输出结果
////            System.out.println(jsonArray.toString());
//        } catch (IOException e) {
//            System.err.println("Error reading file: " + e.getMessage());
//        }
//    }
//
//    private static List<String> splitJson(String rawJson) {
//        List<String> result = new ArrayList<>();
//        int start = 0;
//        int depth = 0;
//
//        for (int i = 0; i < rawJson.length(); i++) {
//            char c = rawJson.charAt(i);
//
//            if (c == '{') {
//                if (depth == 0 && rawJson.startsWith("\"_id", start)) {
//                    start = i;
//                }
//                depth++;
//            } else if (c == '}') {
//                depth--;
//                if (depth == 0) {
//                    String jsonObject = rawJson.substring(start, i + 1);
//                    if (!jsonObject.endsWith("},")) { // 检查是否已经以逗号结尾
//                        jsonObject += ",";
//                    }
//                    result.add(jsonObject);
//                }
//            }
//        }
//
//        return result;
//    }
//}


