package rulecheck;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashSet;
import java.util.Set;
import ruleexec.RuleRegistry;

public final class RuleRegistryCoverageCheck {
  private RuleRegistryCoverageCheck() {}

  public static void main(String[] args) throws IOException {
    Path standard = Path.of("rule_library/standard.txt");
    if (args.length == 1) {
      standard = Path.of(args[0]);
    }

    Set<String> rules = loadRules(standard);
    int mapped = 0;
    int missing = 0;

    for (String rule : rules) {
      if (RuleRegistry.contains(rule)) {
        mapped++;
      } else {
        missing++;
        System.out.println("MISSING RULE: " + rule);
      }
    }

    if (!RuleRegistry.unavailableRules().isEmpty()) {
      System.out.println("UNAVAILABLE (present in registry mapping but not in this Calcite runtime):");
      RuleRegistry.unavailableRules().forEach((name, holder) ->
          System.out.println("  " + name + " -> " + holder));
    }

    System.out.println("total rules: " + rules.size());
    System.out.println("mapped rules: " + mapped);
    System.out.println("missing rules: " + missing);

    if (missing > 0) {
      System.exit(2);
    }
  }

  private static Set<String> loadRules(Path path) throws IOException {
    Set<String> ruleNames = new LinkedHashSet<>();
    for (String rawLine : Files.readAllLines(path)) {
      String line = rawLine.trim();
      if (line.isEmpty() || line.startsWith("#") || line.startsWith("rule_")) {
        continue;
      }
      ruleNames.add(line);
    }
    return ruleNames;
  }
}
