import sys
import os

def goggle_assembly(x_offset=0, y_offset=0, rotation=0, include_flair=False):
    flair_xml = ""
    if include_flair:
        flair_xml = f'''
    <!-- Golden Star Lens Flare -->
    <Shape name="GoggleFlare" x="{255 + x_offset}" y="{110 + y_offset}">
      <Star width="28" height="28" points="4" innerRadius="0.2" cornerRadius="1" /><Fill><SolidColor colorValue="FFFFD700" /></Fill>
    </Shape>'''

    rot_attr = f' rotation="{rotation}"' if rotation != 0 else ''
    
    return f'''
    <!-- GOGGLES COMPLETE HIGH-FIDELITY ASSEMBLY -->{flair_xml}
    <!-- Left Goggle Specular Glass Glints -->
    <Shape name="LeftGoggleGlassGlint1" x="{160 + x_offset}" y="{120 + y_offset}" rotation="{-30 + rotation}">
      <Rectangle width="4" height="22" cornerRadiusTL="2" /><Fill><SolidColor colorValue="DDFFFFFF" /></Fill>
    </Shape>
    <Shape name="LeftGoggleGlassGlint2" x="{168 + x_offset}" y="{126 + y_offset}" rotation="{-30 + rotation}">
      <Rectangle width="2.5" height="12" cornerRadiusTL="1" /><Fill><SolidColor colorValue="99FFFFFF" /></Fill>
    </Shape>
    <!-- Left Goggle Aquamarine Lens -->
    <Shape name="LeftGoggleLens" x="{165 + x_offset}" y="{125 + y_offset}"{rot_attr}>
      <Ellipse width="40" height="40" />
      <Fill>
        <LinearGradient startX="-15" startY="-15" endX="15" endY="15">
          <GradientStop position="0" colorValue="FF0284C7" />
          <GradientStop position="0.5" colorValue="FF38BDF8" />
          <GradientStop position="1" colorValue="FFBAE6FD" />
        </LinearGradient>
      </Fill>
    </Shape>
    <!-- Left Goggle Brass Outer Bevel Rim -->
    <Shape name="LeftGoggleRim" x="{165 + x_offset}" y="{125 + y_offset}"{rot_attr}>
      <Ellipse width="48" height="48" /><Fill><SolidColor colorValue="FFF59E0B" /></Fill>
      <Stroke thickness="3.5">
        <LinearGradient startX="0" startY="-24" endX="0" endY="24">
          <GradientStop position="0" colorValue="FFFDE047" />
          <GradientStop position="1" colorValue="FFB45309" />
        </LinearGradient>
      </Stroke>
    </Shape>

    <!-- Right Goggle Specular Glass Glints -->
    <Shape name="RightGoggleGlassGlint1" x="{250 + x_offset}" y="{120 + y_offset}" rotation="{-30 + rotation}">
      <Rectangle width="4" height="22" cornerRadiusTL="2" /><Fill><SolidColor colorValue="DDFFFFFF" /></Fill>
    </Shape>
    <Shape name="RightGoggleGlassGlint2" x="{258 + x_offset}" y="{126 + y_offset}" rotation="{-30 + rotation}">
      <Rectangle width="2.5" height="12" cornerRadiusTL="1" /><Fill><SolidColor colorValue="99FFFFFF" /></Fill>
    </Shape>
    <!-- Right Goggle Aquamarine Lens -->
    <Shape name="RightGoggleLens" x="{255 + x_offset}" y="{125 + y_offset}"{rot_attr}>
      <Ellipse width="40" height="40" />
      <Fill>
        <LinearGradient startX="-15" startY="-15" endX="15" endY="15">
          <GradientStop position="0" colorValue="FF0284C7" />
          <GradientStop position="0.5" colorValue="FF38BDF8" />
          <GradientStop position="1" colorValue="FFBAE6FD" />
        </LinearGradient>
      </Fill>
    </Shape>
    <!-- Right Goggle Brass Outer Bevel Rim -->
    <Shape name="RightGoggleRim" x="{255 + x_offset}" y="{125 + y_offset}"{rot_attr}>
      <Ellipse width="48" height="48" /><Fill><SolidColor colorValue="FFF59E0B" /></Fill>
      <Stroke thickness="3.5">
        <LinearGradient startX="0" startY="-24" endX="0" endY="24">
          <GradientStop position="0" colorValue="FFFDE047" />
          <GradientStop position="1" colorValue="FFB45309" />
        </LinearGradient>
      </Stroke>
    </Shape>

    <!-- Goggle Bridge & Leather Strap -->
    <Shape name="GoggleBridge" x="{210 + x_offset}" y="{125 + y_offset}"{rot_attr}>
      <Rectangle width="20" height="10" cornerRadiusTL="4" /><Fill><SolidColor colorValue="FFF59E0B" /></Fill>
      <Stroke thickness="2"><SolidColor colorValue="FF78350F" /></Stroke>
    </Shape>
    <Shape name="GoggleStrap" x="{210 + x_offset}" y="{125 + y_offset}"{rot_attr}>
      <Rectangle width="210" height="14" cornerRadiusTL="6" /><Fill><SolidColor colorValue="FF3E2723" /></Fill>
      <Stroke thickness="1.5"><SolidColor colorValue="FF795548" /></Stroke>
    </Shape>
'''

def helmet_assembly(x_offset=0, y_offset=0, rotation=0):
    rot_attr = f' rotation="{rotation}"' if rotation != 0 else ''
    return f'''
    <!-- AVIATOR LEATHER FLIGHT CAP & SHEARLING FLEECE -->
    <Shape name="HelmetFleeceTrim" x="{210 + x_offset}" y="{148 + y_offset}"{rot_attr}>
      <Rectangle width="176" height="18" cornerRadiusTL="9" />
      <Fill>
        <LinearGradient startX="0" startY="-9" endX="0" endY="9">
          <GradientStop position="0" colorValue="FFFFFFFF" />
          <GradientStop position="0.7" colorValue="FFFFF8E1" />
          <GradientStop position="1" colorValue="FFEFEBE9" />
        </LinearGradient>
      </Fill>
      <Stroke thickness="2"><SolidColor colorValue="22000000" /></Stroke>
    </Shape>

    <Shape name="LeftEarflap" x="{115 + x_offset}" y="{165 + y_offset}" rotation="{10 + rotation}">
      <PointsPath isClosed="true">
        <StraightVertex x="-14" y="-25" radius="8" />
        <StraightVertex x="16" y="-25" radius="8" />
        <StraightVertex x="12" y="32" radius="10" />
        <StraightVertex x="-10" y="32" radius="10" />
      </PointsPath>
      <Fill>
        <LinearGradient startX="0" startY="-25" endX="0" endY="32">
          <GradientStop position="0" colorValue="FF5D4037" />
          <GradientStop position="1" colorValue="FF3E2723" />
        </LinearGradient>
      </Fill>
      <Stroke thickness="2"><SolidColor colorValue="FF8D6E63" /></Stroke>
    </Shape>
    <Shape name="LeftEarflapGrommet" x="{116 + x_offset}" y="{185 + y_offset}"{rot_attr}>
      <Ellipse width="10" height="10" /><Fill><SolidColor colorValue="FFF59E0B" /></Fill>
      <Stroke thickness="2"><SolidColor colorValue="FF78350F" /></Stroke>
    </Shape>

    <Shape name="RightEarflap" x="{305 + x_offset}" y="{165 + y_offset}" rotation="{-10 + rotation}">
      <PointsPath isClosed="true">
        <StraightVertex x="-16" y="-25" radius="8" />
        <StraightVertex x="14" y="-25" radius="8" />
        <StraightVertex x="10" y="32" radius="10" />
        <StraightVertex x="-12" y="32" radius="10" />
      </PointsPath>
      <Fill>
        <LinearGradient startX="0" startY="-25" endX="0" endY="32">
          <GradientStop position="0" colorValue="FF5D4037" />
          <GradientStop position="1" colorValue="FF3E2723" />
        </LinearGradient>
      </Fill>
      <Stroke thickness="2"><SolidColor colorValue="FF8D6E63" /></Stroke>
    </Shape>
    <Shape name="RightEarflapGrommet" x="{304 + x_offset}" y="{185 + y_offset}"{rot_attr}>
      <Ellipse width="10" height="10" /><Fill><SolidColor colorValue="FFF59E0B" /></Fill>
      <Stroke thickness="2"><SolidColor colorValue="FF78350F" /></Stroke>
    </Shape>

    <Shape name="HelmetDome" x="{210 + x_offset}" y="{115 + y_offset}"{rot_attr}>
      <PointsPath isClosed="true">
        <StraightVertex x="0" y="-55" radius="45" />
        <StraightVertex x="92" y="-10" radius="40" />
        <StraightVertex x="85" y="36" radius="20" />
        <StraightVertex x="-85" y="36" radius="20" />
        <StraightVertex x="-92" y="-10" radius="40" />
      </PointsPath>
      <Fill>
        <LinearGradient startX="0" startY="-55" endX="0" endY="36">
          <GradientStop position="0" colorValue="FF795548" />
          <GradientStop position="0.4" colorValue="FF5D4037" />
          <GradientStop position="1" colorValue="FF3E2723" />
        </LinearGradient>
      </Fill>
      <Stroke thickness="2.5"><SolidColor colorValue="FF8D6E63" /></Stroke>
    </Shape>

    <Shape name="FlightCrestTuft" x="{210 + x_offset}" y="{55 + y_offset}"{rot_attr}>
      <PointsPath isClosed="true">
        <StraightVertex x="0" y="-16" radius="8" />
        <StraightVertex x="14" y="10" radius="6" />
        <StraightVertex x="-14" y="10" radius="6" />
      </PointsPath>
      <Fill><SolidColor colorValue="FFFFA000" /></Fill>
    </Shape>
'''

def body_assembly(y_offset=0, halo_xml=""):
    return f'''
    <!-- CUSTARD BELLY & DOWNY MARKS -->
    <Shape name="ChestMarking1" x="210" y="{270 + y_offset}"><Ellipse width="22" height="7" /><Fill><SolidColor colorValue="22F57C00" /></Fill></Shape>
    <Shape name="ChestMarking2" x="190" y="{286 + y_offset}"><Ellipse width="18" height="6" /><Fill><SolidColor colorValue="22F57C00" /></Fill></Shape>
    <Shape name="ChestMarking3" x="230" y="{286 + y_offset}"><Ellipse width="18" height="6" /><Fill><SolidColor colorValue="22F57C00" /></Fill></Shape>

    <Shape name="CustardBelly" x="210" y="{282 + y_offset}">
      <PointsPath isClosed="true">
        <StraightVertex x="0" y="-55" radius="45" />
        <StraightVertex x="65" y="-10" radius="45" />
        <StraightVertex x="55" y="55" radius="40" />
        <StraightVertex x="0" y="70" radius="35" />
        <StraightVertex x="-55" y="55" radius="40" />
        <StraightVertex x="-65" y="-10" radius="45" />
      </PointsPath>
      <Fill>
        <LinearGradient startX="0" startY="-55" endX="0" endY="70">
          <GradientStop position="0" colorValue="FFFFFDE7" />
          <GradientStop position="0.5" colorValue="FFFFF9C4" />
          <GradientStop position="1" colorValue="FFFFE082" />
        </LinearGradient>
      </Fill>
    </Shape>

    <!-- MASTER PEAR BODY SILHOUETTE -->
    <Shape name="MasterPearBody" x="210" y="{225 + y_offset}">
      <PointsPath isClosed="true">
        <StraightVertex x="0" y="-140" radius="70" />
        <StraightVertex x="85" y="-60" radius="45" />
        <StraightVertex x="105" y="10" radius="50" />
        <StraightVertex x="95" y="85" radius="55" />
        <StraightVertex x="0" y="130" radius="60" />
        <StraightVertex x="-95" y="85" radius="55" />
        <StraightVertex x="-105" y="10" radius="50" />
        <StraightVertex x="-85" y="-60" radius="45" />
      </PointsPath>
      <Fill>
        <LinearGradient startX="0" startY="-140" endX="0" endY="130">
          <GradientStop position="0" colorValue="FFFFCA28" />
          <GradientStop position="0.3" colorValue="FFFFA000" />
          <GradientStop position="0.75" colorValue="FFF57C00" />
          <GradientStop position="1" colorValue="FFE65100" />
        </LinearGradient>
      </Fill>
      <Stroke thickness="3.5"><SolidColor colorValue="33BF360C" /></Stroke>
    </Shape>

    <!-- LITTLE BIRD FEET -->
    <Shape name="LeftFootToeMiddle" x="175" y="{360 + y_offset}"><Rectangle width="12" height="24" cornerRadiusTL="6" /><Fill><SolidColor colorValue="FFF57C00" /></Fill></Shape>
    <Shape name="LeftFootToeLeft" x="165" y="{362 + y_offset}" rotation="-15"><Rectangle width="10" height="20" cornerRadiusTL="5" /><Fill><SolidColor colorValue="FFF57C00" /></Fill></Shape>
    <Shape name="LeftFootToeRight" x="185" y="{362 + y_offset}" rotation="15"><Rectangle width="10" height="20" cornerRadiusTL="5" /><Fill><SolidColor colorValue="FFF57C00" /></Fill></Shape>

    <Shape name="RightFootToeMiddle" x="245" y="{360 + y_offset}"><Rectangle width="12" height="24" cornerRadiusTL="6" /><Fill><SolidColor colorValue="FFF57C00" /></Fill></Shape>
    <Shape name="RightFootToeLeft" x="235" y="{362 + y_offset}" rotation="-15"><Rectangle width="10" height="20" cornerRadiusTL="5" /><Fill><SolidColor colorValue="FFF57C00" /></Fill></Shape>
    <Shape name="RightFootToeRight" x="255" y="{362 + y_offset}" rotation="15"><Rectangle width="10" height="20" cornerRadiusTL="5" /><Fill><SolidColor colorValue="FFF57C00" /></Fill></Shape>

    <!-- GROUND CONTACT SHADOW -->
    <Shape name="GroundShadow" x="210" y="375">
      <Ellipse width="220" height="24" />
      <Fill>
        <RadialGradient>
          <GradientStop position="0" colorValue="88050914" />
          <GradientStop position="0.6" colorValue="44050914" />
          <GradientStop position="1" colorValue="00050914" />
        </RadialGradient>
      </Fill>
    </Shape>
{halo_xml}
'''

def generate_all():
    lines = ['<Rive version="1" kind="fragment">']

    # =============================================================
    # 1. KITE_MASTER_IDLE
    # =============================================================
    lines.append('  <Artboard name="Kite_Master_Idle" width="420" height="420">')
    lines.append('    <Fill name="CanvasBg"><SolidColor colorValue="FF0B132B" /></Fill>')
    lines.append('''
    <!-- Eye Specular Sparkles -->
    <Shape name="LeftEyeSpecularMain" x="150" y="180"><Ellipse width="16" height="16" /><Fill><SolidColor colorValue="FFFFFFFF" /></Fill></Shape>
    <Shape name="LeftEyeSpecularBounce" x="172" y="208"><Ellipse width="8" height="8" /><Fill><SolidColor colorValue="DDE0F2FE" /></Fill></Shape>
    <Shape name="LeftEyeStarGlint" x="146" y="202"><Star width="7" height="7" points="4" innerRadius="0.3" cornerRadius="1" /><Fill><SolidColor colorValue="FFFFFFFF" /></Fill></Shape>

    <Shape name="RightEyeSpecularMain" x="250" y="180"><Ellipse width="16" height="16" /><Fill><SolidColor colorValue="FFFFFFFF" /></Fill></Shape>
    <Shape name="RightEyeSpecularBounce" x="272" y="208"><Ellipse width="8" height="8" /><Fill><SolidColor colorValue="DDE0F2FE" /></Fill></Shape>
    <Shape name="RightEyeStarGlint" x="246" y="202"><Star width="7" height="7" points="4" innerRadius="0.3" cornerRadius="1" /><Fill><SolidColor colorValue="FFFFFFFF" /></Fill></Shape>

    <!-- Beak -->
    <Shape name="BeakTopShine" x="210" y="209"><Ellipse width="12" height="4" /><Fill><SolidColor colorValue="CCFFFFFF" /></Fill></Shape>
    <Shape name="BeakShape" x="210" y="218">
      <PointsPath isClosed="true">
        <StraightVertex x="0" y="-14" radius="7" />
        <StraightVertex x="18" y="2" radius="5" />
        <StraightVertex x="0" y="18" radius="7" />
        <StraightVertex x="-18" y="2" radius="5" />
      </PointsPath>
      <Fill>
        <LinearGradient startX="0" startY="-14" endX="0" endY="18">
          <GradientStop position="0" colorValue="FFFFA726" />
          <GradientStop position="0.5" colorValue="FFFF7043" />
          <GradientStop position="1" colorValue="FFE64A19" />
        </LinearGradient>
      </Fill>
      <Stroke thickness="2"><SolidColor colorValue="33870000" /></Stroke>
    </Shape>

    <!-- Eyes -->
    <Shape name="LeftEyePupil" x="160" y="195">
      <Ellipse width="46" height="54" />
      <Fill>
        <RadialGradient>
          <GradientStop position="0" colorValue="FF0D0704" />
          <GradientStop position="0.75" colorValue="FF1E120A" />
          <GradientStop position="0.95" colorValue="FFF57C00" />
          <GradientStop position="1" colorValue="FFFFB74D" />
        </RadialGradient>
      </Fill>
    </Shape>
    <Shape name="LeftEyeSocket" x="160" y="195"><Ellipse width="50" height="58" /><Fill><SolidColor colorValue="FF2E1805" /></Fill></Shape>

    <Shape name="RightEyePupil" x="260" y="195">
      <Ellipse width="46" height="54" />
      <Fill>
        <RadialGradient>
          <GradientStop position="0" colorValue="FF0D0704" />
          <GradientStop position="0.75" colorValue="FF1E120A" />
          <GradientStop position="0.95" colorValue="FFF57C00" />
          <GradientStop position="1" colorValue="FFFFB74D" />
        </RadialGradient>
      </Fill>
    </Shape>
    <Shape name="RightEyeSocket" x="260" y="195"><Ellipse width="50" height="58" /><Fill><SolidColor colorValue="FF2E1805" /></Fill></Shape>

    <!-- Cheeks & Face Mask -->
    <Shape name="LeftCheekBlush" x="122" y="222"><Ellipse width="34" height="20" /><Fill><SolidColor colorValue="77FF7043" /></Fill></Shape>
    <Shape name="RightCheekBlush" x="298" y="222"><Ellipse width="34" height="20" /><Fill><SolidColor colorValue="77FF7043" /></Fill></Shape>

    <Shape name="FaceMask" x="210" y="200">
      <PointsPath isClosed="true">
        <StraightVertex x="0" y="-45" radius="25" />
        <StraightVertex x="82" y="-15" radius="35" />
        <StraightVertex x="92" y="25" radius="30" />
        <StraightVertex x="0" y="52" radius="25" />
        <StraightVertex x="-92" y="25" radius="30" />
        <StraightVertex x="-82" y="-15" radius="35" />
      </PointsPath>
      <Fill>
        <LinearGradient startX="0" startY="-45" endX="0" endY="52">
          <GradientStop position="0" colorValue="FFFFF9C4" />
          <GradientStop position="0.6" colorValue="FFFFF8E1" />
          <GradientStop position="1" colorValue="FFFFECB3" />
        </LinearGradient>
      </Fill>
    </Shape>
''')
    lines.append(goggle_assembly())
    lines.append(helmet_assembly())
    lines.append('''
    <!-- Cozy Folded Wings on Flanks -->
    <Shape name="LeftWing" x="122" y="280" rotation="10">
      <PointsPath isClosed="true">
        <StraightVertex x="0" y="-45" radius="25" />
        <StraightVertex x="22" y="-10" radius="18" />
        <StraightVertex x="15" y="42" radius="10" />
        <StraightVertex x="-2" y="46" radius="10" />
        <StraightVertex x="-18" y="32" radius="12" />
        <StraightVertex x="-22" y="-10" radius="20" />
      </PointsPath>
      <Fill>
        <LinearGradient startX="0" startY="-45" endX="0" endY="46">
          <GradientStop position="0" colorValue="FFFFA000" />
          <GradientStop position="0.5" colorValue="FFF57C00" />
          <GradientStop position="1" colorValue="FFE65100" />
        </LinearGradient>
      </Fill>
      <Stroke thickness="2.5"><SolidColor colorValue="33D84315" /></Stroke>
    </Shape>

    <Shape name="RightWing" x="298" y="280" rotation="-10">
      <PointsPath isClosed="true">
        <StraightVertex x="0" y="-45" radius="25" />
        <StraightVertex x="22" y="-10" radius="20" />
        <StraightVertex x="18" y="32" radius="12" />
        <StraightVertex x="2" y="46" radius="10" />
        <StraightVertex x="-15" y="42" radius="10" />
        <StraightVertex x="-22" y="-10" radius="18" />
      </PointsPath>
      <Fill>
        <LinearGradient startX="0" startY="-45" endX="0" endY="46">
          <GradientStop position="0" colorValue="FFFFA000" />
          <GradientStop position="0.5" colorValue="FFF57C00" />
          <GradientStop position="1" colorValue="FFE65100" />
        </LinearGradient>
      </Fill>
      <Stroke thickness="2.5"><SolidColor colorValue="33D84315" /></Stroke>
    </Shape>
''')
    lines.append(body_assembly())
    lines.append('  </Artboard>')

    # =============================================================
    # 2. KITE_MASTER_VICTORY
    # =============================================================
    lines.append('  <Artboard name="Kite_Master_Victory" width="420" height="420">')
    lines.append('    <Fill name="CanvasBg"><SolidColor colorValue="FF0B132B" /></Fill>')
    lines.append('''
    <!-- Celebration Sparkles & Confetti (Floating cleanly around character) -->
    <Shape name="StarGold1" x="65" y="90"><Star width="20" height="20" points="4" innerRadius="0.3" cornerRadius="2" /><Fill><SolidColor colorValue="FFFFD700" /></Fill></Shape>
    <Shape name="StarGold2" x="355" y="80"><Star width="22" height="22" points="4" innerRadius="0.3" cornerRadius="2" /><Fill><SolidColor colorValue="FFFFD700" /></Fill></Shape>
    <Shape name="StarCyan" x="350" y="170"><Star width="14" height="14" points="4" innerRadius="0.3" cornerRadius="2" /><Fill><SolidColor colorValue="FF00E5FF" /></Fill></Shape>
    <Shape name="ConfettiPink1" x="55" y="160" rotation="35"><Rectangle width="8" height="16" cornerRadiusTL="3" /><Fill><SolidColor colorValue="FFFF4081" /></Fill></Shape>
    <Shape name="ConfettiPink2" x="360" y="240" rotation="-25"><Rectangle width="8" height="16" cornerRadiusTL="3" /><Fill><SolidColor colorValue="FFFF4081" /></Fill></Shape>
    <Shape name="ConfettiGreen" x="65" y="260" rotation="-15"><Rectangle width="8" height="16" cornerRadiusTL="3" /><Fill><SolidColor colorValue="FF00E676" /></Fill></Shape>

    <!-- Joyous Smiling Eyes (^ ^) -->
    <Shape name="LeftHappyEye" x="160" y="175">
      <PointsPath isClosed="false">
        <StraightVertex x="-18" y="10" radius="0" />
        <StraightVertex x="0" y="-8" radius="10" />
        <StraightVertex x="18" y="10" radius="0" />
      </PointsPath>
      <Stroke thickness="5"><SolidColor colorValue="FF2E1805" /></Stroke>
    </Shape>
    <Shape name="RightHappyEye" x="260" y="175">
      <PointsPath isClosed="false">
        <StraightVertex x="-18" y="10" radius="0" />
        <StraightVertex x="0" y="-8" radius="10" />
        <StraightVertex x="18" y="10" radius="0" />
      </PointsPath>
      <Stroke thickness="5"><SolidColor colorValue="FF2E1805" /></Stroke>
    </Shape>

    <!-- Joyous Open Beak Chirp -->
    <Shape name="MouthOpenCavity" x="210" y="202">
      <PointsPath isClosed="true">
        <StraightVertex x="0" y="-12" radius="4" />
        <StraightVertex x="16" y="2" radius="4" />
        <StraightVertex x="0" y="16" radius="6" />
        <StraightVertex x="-16" y="2" radius="4" />
      </PointsPath>
      <Fill><SolidColor colorValue="FF880E4F" /></Fill>
    </Shape>
    <Shape name="MouthTongue" x="210" y="208">
      <Ellipse width="14" height="10" /><Fill><SolidColor colorValue="FFFF4081" /></Fill>
    </Shape>
    <Shape name="BeakUpperRim" x="210" y="196">
      <PointsPath isClosed="true">
        <StraightVertex x="0" y="-8" radius="4" />
        <StraightVertex x="16" y="4" radius="3" />
        <StraightVertex x="-16" y="4" radius="3" />
      </PointsPath>
      <Fill><SolidColor colorValue="FFFFA726" /></Fill>
    </Shape>

    <!-- Cheeks & Face Mask -->
    <Shape name="LeftCheekBlush" x="122" y="202"><Ellipse width="34" height="20" /><Fill><SolidColor colorValue="99FF4081" /></Fill></Shape>
    <Shape name="RightCheekBlush" x="298" y="202"><Ellipse width="34" height="20" /><Fill><SolidColor colorValue="99FF4081" /></Fill></Shape>

    <Shape name="FaceMask" x="210" y="180">
      <PointsPath isClosed="true">
        <StraightVertex x="0" y="-45" radius="25" />
        <StraightVertex x="82" y="-15" radius="35" />
        <StraightVertex x="92" y="25" radius="30" />
        <StraightVertex x="0" y="52" radius="25" />
        <StraightVertex x="-92" y="25" radius="30" />
        <StraightVertex x="-82" y="-15" radius="35" />
      </PointsPath>
      <Fill>
        <LinearGradient startX="0" startY="-45" endX="0" endY="52">
          <GradientStop position="0" colorValue="FFFFF9C4" />
          <GradientStop position="0.6" colorValue="FFFFF8E1" />
          <GradientStop position="1" colorValue="FFFFECB3" />
        </LinearGradient>
      </Fill>
    </Shape>
''')
    lines.append(goggle_assembly(y_offset=-20))
    lines.append(helmet_assembly(y_offset=-20))
    lines.append('''
    <!-- TRIUMPHANT HIGH WINGS (Raised Up in Joy) -->
    <Shape name="LeftWingHigh" x="95" y="190" rotation="-50">
      <PointsPath isClosed="true">
        <StraightVertex x="0" y="-55" radius="20" />
        <StraightVertex x="25" y="-10" radius="16" />
        <StraightVertex x="20" y="45" radius="10" />
        <StraightVertex x="-2" y="50" radius="10" />
        <StraightVertex x="-20" y="35" radius="12" />
        <StraightVertex x="-25" y="-10" radius="18" />
      </PointsPath>
      <Fill><LinearGradient startX="0" startY="-55" endX="0" endY="50"><GradientStop position="0" colorValue="FFFFA000" /><GradientStop position="1" colorValue="FFE65100" /></LinearGradient></Fill>
      <Stroke thickness="2.5"><SolidColor colorValue="33D84315" /></Stroke>
    </Shape>

    <Shape name="RightWingHigh" x="325" y="190" rotation="50">
      <PointsPath isClosed="true">
        <StraightVertex x="0" y="-55" radius="20" />
        <StraightVertex x="25" y="-10" radius="18" />
        <StraightVertex x="20" y="35" radius="12" />
        <StraightVertex x="2" y="50" radius="10" />
        <StraightVertex x="-20" y="45" radius="10" />
        <StraightVertex x="-25" y="-10" radius="16" />
      </PointsPath>
      <Fill><LinearGradient startX="0" startY="-55" endX="0" endY="50"><GradientStop position="0" colorValue="FFFFA000" /><GradientStop position="1" colorValue="FFE65100" /></LinearGradient></Fill>
      <Stroke thickness="2.5"><SolidColor colorValue="33D84315" /></Stroke>
    </Shape>
''')
    lines.append(body_assembly(y_offset=-20))
    lines.append('  </Artboard>')

    # =============================================================
    # 3. KITE_MASTER_PEEKABOO (Irresistibly Cute Wings Over Face)
    # =============================================================
    lines.append('  <Artboard name="Kite_Master_Peekaboo" width="420" height="420">')
    lines.append('    <Fill name="CanvasBg"><SolidColor colorValue="FF0B132B" /></Fill>')
    lines.append('''
    <!-- FOREMOST: SCULPTED 3-FEATHER WINGS WRAPPED FROM SHOULDERS -->
    <!-- Left Wing (Originating at Left Flank x=115, y=260, curving over face) -->
    <Shape name="CoverLeftWing" x="145" y="240">
      <PointsPath isClosed="true">
        <!-- Flank base -->
        <StraightVertex x="-35" y="40" radius="20" />
        <StraightVertex x="-30" y="-20" radius="22" />
        <!-- Feather tips curving inward over left eye and beak -->
        <StraightVertex x="20" y="-35" radius="12" />
        <StraightVertex x="45" y="-10" radius="10" />
        <StraightVertex x="35" y="20" radius="12" />
        <StraightVertex x="10" y="45" radius="16" />
      </PointsPath>
      <Fill>
        <LinearGradient startX="-35" startY="-20" endX="45" endY="45">
          <GradientStop position="0" colorValue="FFFFA000" />
          <GradientStop position="0.5" colorValue="FFF57C00" />
          <GradientStop position="1" colorValue="FFE65100" />
        </LinearGradient>
      </Fill>
      <Stroke thickness="2.5"><SolidColor colorValue="33D84315" /></Stroke>
    </Shape>

    <!-- Right Wing (Originating at Right Flank x=305, y=260, tucked under eye) -->
    <Shape name="CoverRightWing" x="275" y="250">
      <PointsPath isClosed="true">
        <!-- Flank base -->
        <StraightVertex x="35" y="35" radius="20" />
        <StraightVertex x="25" y="-20" radius="20" />
        <!-- Feather tips peeking under eye -->
        <StraightVertex x="-20" y="-30" radius="10" />
        <StraightVertex x="-40" y="-5" radius="10" />
        <StraightVertex x="-30" y="25" radius="12" />
        <StraightVertex x="-5" y="45" radius="16" />
      </PointsPath>
      <Fill>
        <LinearGradient startX="35" startY="-20" endX="-40" endY="45">
          <GradientStop position="0" colorValue="FFFFA000" />
          <GradientStop position="0.5" colorValue="FFF57C00" />
          <GradientStop position="1" colorValue="FFE65100" />
        </LinearGradient>
      </Fill>
      <Stroke thickness="2.5"><SolidColor colorValue="33D84315" /></Stroke>
    </Shape>

    <!-- ONE GIANT GLOSSY ANIME EYE PEEKING OVER WING -->
    <Shape name="RightEyeSpecularMain" x="250" y="180"><Ellipse width="16" height="16" /><Fill><SolidColor colorValue="FFFFFFFF" /></Fill></Shape>
    <Shape name="RightEyeSpecularBounce" x="272" y="208"><Ellipse width="8" height="8" /><Fill><SolidColor colorValue="DDE0F2FE" /></Fill></Shape>
    <Shape name="RightEyeStarGlint" x="246" y="202"><Star width="7" height="7" points="4" innerRadius="0.3" cornerRadius="1" /><Fill><SolidColor colorValue="FFFFFFFF" /></Fill></Shape>

    <Shape name="RightEyePupil" x="260" y="195">
      <Ellipse width="46" height="54" />
      <Fill>
        <RadialGradient>
          <GradientStop position="0" colorValue="FF0D0704" />
          <GradientStop position="0.75" colorValue="FF1E120A" />
          <GradientStop position="0.95" colorValue="FFF57C00" />
          <GradientStop position="1" colorValue="FFFFB74D" />
        </RadialGradient>
      </Fill>
    </Shape>
    <Shape name="RightEyeSocket" x="260" y="195"><Ellipse width="50" height="58" /><Fill><SolidColor colorValue="FF2E1805" /></Fill></Shape>

    <!-- Deep Rosy Anime Blush & Steam Dashes -->
    <Shape name="FlusteredBlushLeft" x="120" y="218"><Ellipse width="38" height="22" /><Fill><SolidColor colorValue="AAFF1744" /></Fill></Shape>
    <Shape name="FlusteredBlushRight" x="300" y="218"><Ellipse width="38" height="22" /><Fill><SolidColor colorValue="AAFF1744" /></Fill></Shape>
    <Shape name="BlushSteam1" x="308" y="192" rotation="20"><Rectangle width="3" height="12" cornerRadiusTL="1.5" /><Fill><SolidColor colorValue="EEFFFFFF" /></Fill></Shape>
    <Shape name="BlushSteam2" x="318" y="196" rotation="25"><Rectangle width="3" height="9" cornerRadiusTL="1.5" /><Fill><SolidColor colorValue="EEFFFFFF" /></Fill></Shape>

    <!-- Face Mask (Beak hidden shyly behind fluffy wings) -->
    <Shape name="FaceMask" x="210" y="200">
      <PointsPath isClosed="true">
        <StraightVertex x="0" y="-45" radius="25" />
        <StraightVertex x="82" y="-15" radius="35" />
        <StraightVertex x="92" y="25" radius="30" />
        <StraightVertex x="0" y="52" radius="25" />
        <StraightVertex x="-92" y="25" radius="30" />
        <StraightVertex x="-82" y="-15" radius="35" />
      </PointsPath>
      <Fill><SolidColor colorValue="FFFFF8E1" /></Fill>
    </Shape>
''')
    lines.append(goggle_assembly())
    lines.append(helmet_assembly())
    lines.append(body_assembly())
    lines.append('  </Artboard>')

    # =============================================================
    # 4. KITE_MASTER_THINKING (Continuous Wing to Chin & Clean Hologram)
    # =============================================================
    lines.append('  <Artboard name="Kite_Master_Thinking" width="420" height="420">')
    lines.append('    <Fill name="CanvasBg"><SolidColor colorValue="FF0B132B" /></Fill>')
    lines.append('''
    <!-- Glowing Holographic AI Orbit & Spark (Floating cleanly in air) -->
    <Shape name="OrbitRing" x="115" y="70" rotation="-20">
      <Ellipse width="55" height="24" /><Fill><SolidColor colorValue="00000000" /></Fill>
      <Stroke thickness="2"><SolidColor colorValue="AA00E5FF" /></Stroke>
    </Shape>
    <Shape name="OrbitNode" x="138" y="62">
      <Ellipse width="8" height="8" /><Fill><SolidColor colorValue="FF00E5FF" /></Fill>
    </Shape>
    <Shape name="OrbitSpark" x="110" y="50">
      <Star width="14" height="14" points="4" innerRadius="0.25" cornerRadius="1" /><Fill><SolidColor colorValue="FFFFD700" /></Fill>
    </Shape>

    <!-- RIGHT WING TAPPING CHIN (Organic curve continuous from right flank) -->
    <Shape name="RightWingChinTap" x="275" y="255">
      <PointsPath isClosed="true">
        <!-- Shoulder flank origin -->
        <StraightVertex x="35" y="25" radius="20" />
        <StraightVertex x="20" y="-15" radius="18" />
        <!-- Reaching inward to touch lower beak -->
        <StraightVertex x="-30" y="-35" radius="10" />
        <StraightVertex x="-48" y="-15" radius="10" />
        <StraightVertex x="-35" y="15" radius="14" />
        <StraightVertex x="5" y="38" radius="18" />
      </PointsPath>
      <Fill>
        <LinearGradient startX="35" startY="25" endX="-48" endY="-35">
          <GradientStop position="0" colorValue="FFFFA000" />
          <GradientStop position="0.5" colorValue="FFF57C00" />
          <GradientStop position="1" colorValue="FFE65100" />
        </LinearGradient>
      </Fill>
      <Stroke thickness="2.5"><SolidColor colorValue="33D84315" /></Stroke>
    </Shape>

    <!-- EYES GLANCING UPWARD-RIGHT (Thoughtful / Contemplative) -->
    <Shape name="LeftEyeSpecularMain" x="162" y="172"><Ellipse width="14" height="14" /><Fill><SolidColor colorValue="FFFFFFFF" /></Fill></Shape>
    <Shape name="RightEyeSpecularMain" x="262" y="172"><Ellipse width="14" height="14" /><Fill><SolidColor colorValue="FFFFFFFF" /></Fill></Shape>

    <Shape name="LeftEyePupil" x="168" y="188">
      <Ellipse width="40" height="48" />
      <Fill>
        <RadialGradient>
          <GradientStop position="0" colorValue="FF0D0704" />
          <GradientStop position="0.8" colorValue="FF1E120A" />
          <GradientStop position="0.95" colorValue="FFF57C00" />
          <GradientStop position="1" colorValue="FFFFB74D" />
        </RadialGradient>
      </Fill>
    </Shape>
    <Shape name="LeftEyeSocket" x="160" y="195"><Ellipse width="50" height="58" /><Fill><SolidColor colorValue="FF2E1805" /></Fill></Shape>

    <Shape name="RightEyePupil" x="268" y="188">
      <Ellipse width="40" height="48" />
      <Fill>
        <RadialGradient>
          <GradientStop position="0" colorValue="FF0D0704" />
          <GradientStop position="0.8" colorValue="FF1E120A" />
          <GradientStop position="0.95" colorValue="FFF57C00" />
          <GradientStop position="1" colorValue="FFFFB74D" />
        </RadialGradient>
      </Fill>
    </Shape>
    <Shape name="RightEyeSocket" x="260" y="195"><Ellipse width="50" height="58" /><Fill><SolidColor colorValue="FF2E1805" /></Fill></Shape>

    <!-- Curious Beak -->
    <Shape name="BeakShape" x="210" y="218" rotation="6">
      <PointsPath isClosed="true">
        <StraightVertex x="0" y="-14" radius="7" />
        <StraightVertex x="18" y="2" radius="5" />
        <StraightVertex x="0" y="18" radius="7" />
        <StraightVertex x="-18" y="2" radius="5" />
      </PointsPath>
      <Fill><SolidColor colorValue="FFFFA726" /></Fill>
    </Shape>

    <!-- Cheeks & Face Mask -->
    <Shape name="LeftCheekBlush" x="122" y="222"><Ellipse width="34" height="20" /><Fill><SolidColor colorValue="77FF7043" /></Fill></Shape>
    <Shape name="RightCheekBlush" x="298" y="222"><Ellipse width="34" height="20" /><Fill><SolidColor colorValue="77FF7043" /></Fill></Shape>

    <Shape name="FaceMask" x="210" y="200">
      <PointsPath isClosed="true">
        <StraightVertex x="0" y="-45" radius="25" />
        <StraightVertex x="82" y="-15" radius="35" />
        <StraightVertex x="92" y="25" radius="30" />
        <StraightVertex x="0" y="52" radius="25" />
        <StraightVertex x="-92" y="25" radius="30" />
        <StraightVertex x="-82" y="-15" radius="35" />
      </PointsPath>
      <Fill><SolidColor colorValue="FFFFF8E1" /></Fill>
    </Shape>
''')
    lines.append(goggle_assembly(rotation=-6))
    lines.append(helmet_assembly(rotation=-6))
    lines.append('''
    <!-- Relaxed Left Wing -->
    <Shape name="LeftWing" x="122" y="280" rotation="10">
      <PointsPath isClosed="true">
        <StraightVertex x="0" y="-45" radius="25" />
        <StraightVertex x="22" y="-10" radius="18" />
        <StraightVertex x="15" y="42" radius="10" />
        <StraightVertex x="-2" y="46" radius="10" />
        <StraightVertex x="-18" y="32" radius="12" />
        <StraightVertex x="-22" y="-10" radius="20" />
      </PointsPath>
      <Fill><SolidColor colorValue="FFFFA000" /></Fill>
      <Stroke thickness="2.5"><SolidColor colorValue="33D84315" /></Stroke>
    </Shape>
''')
    lines.append(body_assembly())
    lines.append('  </Artboard>')

    # =============================================================
    # 5. KITE_MASTER_FROZEN (Missed Daily Goal / Broken Streak)
    # =============================================================
    lines.append('  <Artboard name="Kite_Master_Frozen" width="420" height="420">')
    lines.append('    <Fill name="CanvasBg"><SolidColor colorValue="FF0B132B" /></Fill>')
    lines.append('''
    <!-- FOREMOST: ICE CUBE BEVELED BLOCK & SURFACE FRACTURES -->
    <Shape name="IceCrack1" x="170" y="170" rotation="-15">
      <PointsPath isClosed="false">
        <StraightVertex x="-40" y="-30" radius="0" />
        <StraightVertex x="-10" y="-5" radius="0" />
        <StraightVertex x="5" y="-15" radius="0" />
        <StraightVertex x="35" y="25" radius="0" />
      </PointsPath>
      <Stroke thickness="3"><SolidColor colorValue="EEFFFFFF" /></Stroke>
    </Shape>
    <Shape name="IceCrack2" x="260" y="260" rotation="20">
      <PointsPath isClosed="false">
        <StraightVertex x="-30" y="-20" radius="0" />
        <StraightVertex x="0" y="0" radius="0" />
        <StraightVertex x="25" y="-10" radius="0" />
      </PointsPath>
      <Stroke thickness="2.5"><SolidColor colorValue="EEFFFFFF" /></Stroke>
    </Shape>

    <!-- Translucent Beveled Ice Crystal Block -->
    <Shape name="IceCubeBlock" x="210" y="225">
      <Rectangle width="310" height="340" cornerRadiusTL="24" />
      <Fill>
        <LinearGradient startX="-155" startY="-170" endX="155" endY="170">
          <GradientStop position="0" colorValue="55E0F2FE" />
          <GradientStop position="0.5" colorValue="3338BDF8" />
          <GradientStop position="1" colorValue="660284C7" />
        </LinearGradient>
      </Fill>
      <Stroke thickness="4">
        <LinearGradient startX="-155" startY="-170" endX="155" endY="170">
          <GradientStop position="0" colorValue="DDFFFFFF" />
          <GradientStop position="1" colorValue="8838BDF8" />
        </LinearGradient>
      </Stroke>
    </Shape>

    <!-- Hanging Icicles from Brow -->
    <Shape name="Icicle1" x="160" y="160"><Triangle width="10" height="24" /><Fill><SolidColor colorValue="EEBAE6FD" /></Fill></Shape>
    <Shape name="Icicle2" x="180" y="162"><Triangle width="8" height="18" /><Fill><SolidColor colorValue="EEBAE6FD" /></Fill></Shape>
    <Shape name="Icicle3" x="240" y="162"><Triangle width="8" height="18" /><Fill><SolidColor colorValue="EEBAE6FD" /></Fill></Shape>
    <Shape name="Icicle4" x="260" y="160"><Triangle width="10" height="24" /><Fill><SolidColor colorValue="EEBAE6FD" /></Fill></Shape>

    <!-- SAD TEARY SHIVERING PUPPY EYES -->
    <Shape name="TearDropLeft" x="142" y="218"><Ellipse width="12" height="16" /><Fill><SolidColor colorValue="EE38BDF8" /></Fill></Shape>
    <Shape name="TearDropRight" x="278" y="218"><Ellipse width="12" height="16" /><Fill><SolidColor colorValue="EE38BDF8" /></Fill></Shape>

    <Shape name="LeftEyeSpecularMain" x="150" y="184"><Ellipse width="12" height="12" /><Fill><SolidColor colorValue="FFFFFFFF" /></Fill></Shape>
    <Shape name="RightEyeSpecularMain" x="250" y="184"><Ellipse width="12" height="12" /><Fill><SolidColor colorValue="FFFFFFFF" /></Fill></Shape>

    <Shape name="LeftEyePupil" x="160" y="196"><Ellipse width="44" height="50" /><Fill><SolidColor colorValue="FF0D0704" /></Fill></Shape>
    <Shape name="LeftEyeSocket" x="160" y="195"><Ellipse width="50" height="58" /><Fill><SolidColor colorValue="FF2E1805" /></Fill></Shape>

    <Shape name="RightEyePupil" x="260" y="196"><Ellipse width="44" height="50" /><Fill><SolidColor colorValue="FF0D0704" /></Fill></Shape>
    <Shape name="RightEyeSocket" x="260" y="195"><Ellipse width="50" height="58" /><Fill><SolidColor colorValue="FF2E1805" /></Fill></Shape>

    <!-- Quivering Pale Beak -->
    <Shape name="BeakShape" x="210" y="218">
      <PointsPath isClosed="true">
        <StraightVertex x="0" y="-12" radius="6" />
        <StraightVertex x="16" y="2" radius="4" />
        <StraightVertex x="0" y="16" radius="6" />
        <StraightVertex x="-16" y="2" radius="4" />
      </PointsPath>
      <Fill><SolidColor colorValue="FFFFA726" /></Fill>
    </Shape>

    <!-- Cold Shivering Cheeks -->
    <Shape name="LeftCheekCold" x="122" y="222"><Ellipse width="34" height="20" /><Fill><SolidColor colorValue="6680D8FF" /></Fill></Shape>
    <Shape name="RightCheekCold" x="298" y="222"><Ellipse width="34" height="20" /><Fill><SolidColor colorValue="6680D8FF" /></Fill></Shape>

    <Shape name="FaceMask" x="210" y="200">
      <PointsPath isClosed="true">
        <StraightVertex x="0" y="-45" radius="25" />
        <StraightVertex x="82" y="-15" radius="35" />
        <StraightVertex x="92" y="25" radius="30" />
        <StraightVertex x="0" y="52" radius="25" />
        <StraightVertex x="-92" y="25" radius="30" />
        <StraightVertex x="-82" y="-15" radius="35" />
      </PointsPath>
      <Fill><SolidColor colorValue="FFE0F2FE" /></Fill>
    </Shape>
''')
    lines.append(goggle_assembly())
    lines.append(helmet_assembly())
    lines.append('''
    <!-- Shivering Tucked Wings -->
    <Shape name="LeftWing" x="122" y="280" rotation="10">
      <PointsPath isClosed="true">
        <StraightVertex x="0" y="-45" radius="25" />
        <StraightVertex x="22" y="-10" radius="18" />
        <StraightVertex x="15" y="42" radius="10" />
        <StraightVertex x="-2" y="46" radius="10" />
        <StraightVertex x="-18" y="32" radius="12" />
        <StraightVertex x="-22" y="-10" radius="20" />
      </PointsPath>
      <Fill><SolidColor colorValue="FFFFA000" /></Fill>
      <Stroke thickness="2.5"><SolidColor colorValue="33D84315" /></Stroke>
    </Shape>

    <Shape name="RightWing" x="298" y="280" rotation="-10">
      <PointsPath isClosed="true">
        <StraightVertex x="0" y="-45" radius="25" />
        <StraightVertex x="22" y="-10" radius="20" />
        <StraightVertex x="18" y="32" radius="12" />
        <StraightVertex x="2" y="46" radius="10" />
        <StraightVertex x="-15" y="42" radius="10" />
        <StraightVertex x="-22" y="-10" radius="18" />
      </PointsPath>
      <Fill><SolidColor colorValue="FFFFA000" /></Fill>
      <Stroke thickness="2.5"><SolidColor colorValue="33D84315" /></Stroke>
    </Shape>
''')
    lines.append(body_assembly())
    lines.append('  </Artboard>')

    # =============================================================
    # 6. KITE_MASTER_ADJUDICATOR (Heroic GovStack Wax Seal)
    # =============================================================
    lines.append('  <Artboard name="Kite_Master_Adjudicator" width="420" height="420">')
    lines.append('    <Fill name="CanvasBg"><SolidColor colorValue="FF0B132B" /></Fill>')
    lines.append('''
    <!-- FOREMOST: EMERALD GOVSTACK OFFICIAL STAMP MEDALLION -->
    <Shape name="RibbonTail1" x="328" y="280" rotation="15">
      <Rectangle width="12" height="38" cornerRadiusTL="3" /><Fill><SolidColor colorValue="FFE53935" /></Fill>
    </Shape>
    <Shape name="RibbonTail2" x="346" y="285" rotation="25">
      <Rectangle width="12" height="34" cornerRadiusTL="3" /><Fill><SolidColor colorValue="FFC62828" /></Fill>
    </Shape>

    <Shape name="EmeraldSealCenter" x="336" y="240">
      <Ellipse width="46" height="46" />
      <Fill><SolidColor colorValue="FF00E676" /></Fill>
      <Stroke thickness="3.5"><SolidColor colorValue="FFFFD700" /></Stroke>
    </Shape>
    <Shape name="SealStar" x="336" y="240">
      <Star width="22" height="22" points="5" innerRadius="0.5" cornerRadius="1" /><Fill><SolidColor colorValue="FFFFFFFF" /></Fill>
    </Shape>
    <Shape name="StampHandle" x="336" y="195">
      <Rectangle width="14" height="50" cornerRadiusTL="6" /><Fill><SolidColor colorValue="FFF59E0B" /></Fill>
      <Stroke thickness="2"><SolidColor colorValue="FFB45309" /></Stroke>
    </Shape>

    <!-- Right Wing Wielding Stamp Firmly (Extending cleanly from shoulder) -->
    <Shape name="RightWingStamp" x="295" y="245">
      <PointsPath isClosed="true">
        <!-- Shoulder -->
        <StraightVertex x="20" y="25" radius="18" />
        <StraightVertex x="0" y="-35" radius="18" />
        <!-- Wing hand grasping handle -->
        <StraightVertex x="35" y="-15" radius="10" />
        <StraightVertex x="45" y="5" radius="10" />
        <StraightVertex x="35" y="25" radius="12" />
        <StraightVertex x="15" y="35" radius="16" />
      </PointsPath>
      <Fill><LinearGradient startX="0" startY="-35" endX="45" endY="35"><GradientStop position="0" colorValue="FFFFA000" /><GradientStop position="1" colorValue="FFE65100" /></LinearGradient></Fill>
      <Stroke thickness="2.5"><SolidColor colorValue="33D84315" /></Stroke>
    </Shape>

    <!-- CONFIDENT HEROIC EYES WITH VIBRANT SPARKLE -->
    <Shape name="LeftEyeSpecularMain" x="150" y="180"><Ellipse width="16" height="16" /><Fill><SolidColor colorValue="FFFFFFFF" /></Fill></Shape>
    <Shape name="LeftEyeSpecularBounce" x="172" y="208"><Ellipse width="8" height="8" /><Fill><SolidColor colorValue="DDE0F2FE" /></Fill></Shape>
    <Shape name="RightEyeSpecularMain" x="250" y="180"><Ellipse width="16" height="16" /><Fill><SolidColor colorValue="FFFFFFFF" /></Fill></Shape>
    <Shape name="RightEyeSpecularBounce" x="272" y="208"><Ellipse width="8" height="8" /><Fill><SolidColor colorValue="DDE0F2FE" /></Fill></Shape>

    <Shape name="LeftEyePupil" x="160" y="195">
      <Ellipse width="46" height="54" />
      <Fill>
        <RadialGradient>
          <GradientStop position="0" colorValue="FF0D0704" />
          <GradientStop position="0.75" colorValue="FF1E120A" />
          <GradientStop position="0.95" colorValue="FFF57C00" />
          <GradientStop position="1" colorValue="FFFFB74D" />
        </RadialGradient>
      </Fill>
    </Shape>
    <Shape name="LeftEyeSocket" x="160" y="195"><Ellipse width="50" height="58" /><Fill><SolidColor colorValue="FF2E1805" /></Fill></Shape>

    <Shape name="RightEyePupil" x="260" y="195">
      <Ellipse width="46" height="54" />
      <Fill>
        <RadialGradient>
          <GradientStop position="0" colorValue="FF0D0704" />
          <GradientStop position="0.75" colorValue="FF1E120A" />
          <GradientStop position="0.95" colorValue="FFF57C00" />
          <GradientStop position="1" colorValue="FFFFB74D" />
        </RadialGradient>
      </Fill>
    </Shape>
    <Shape name="RightEyeSocket" x="260" y="195"><Ellipse width="50" height="58" /><Fill><SolidColor colorValue="FF2E1805" /></Fill></Shape>

    <!-- Confident Heroic Brows (Angled determined eyebrows slanted down towards nose) -->
    <Shape name="LeftHeroicBrow" x="160" y="166" rotation="-15">
      <Rectangle width="36" height="7" cornerRadiusTL="3.5" /><Fill><SolidColor colorValue="FF5D4037" /></Fill>
    </Shape>
    <Shape name="RightHeroicBrow" x="260" y="166" rotation="15">
      <Rectangle width="36" height="7" cornerRadiusTL="3.5" /><Fill><SolidColor colorValue="FF5D4037" /></Fill>
    </Shape>

    <!-- Beak -->
    <Shape name="BeakShape" x="210" y="218">
      <PointsPath isClosed="true">
        <StraightVertex x="0" y="-14" radius="7" />
        <StraightVertex x="18" y="2" radius="5" />
        <StraightVertex x="0" y="18" radius="7" />
        <StraightVertex x="-18" y="2" radius="5" />
      </PointsPath>
      <Fill><SolidColor colorValue="FFFFA726" /></Fill>
    </Shape>

    <!-- Face Mask -->
    <Shape name="FaceMask" x="210" y="200">
      <PointsPath isClosed="true">
        <StraightVertex x="0" y="-45" radius="25" />
        <StraightVertex x="82" y="-15" radius="35" />
        <StraightVertex x="92" y="25" radius="30" />
        <StraightVertex x="0" y="52" radius="25" />
        <StraightVertex x="-92" y="25" radius="30" />
        <StraightVertex x="-82" y="-15" radius="35" />
      </PointsPath>
      <Fill><SolidColor colorValue="FFFFF8E1" /></Fill>
    </Shape>
''')
    lines.append(goggle_assembly(include_flair=True))
    lines.append(helmet_assembly())
    lines.append('''
    <!-- Left Wing (Firmly on Hip) -->
    <Shape name="LeftWingHip" x="115" y="275" rotation="15">
      <PointsPath isClosed="true">
        <StraightVertex x="0" y="-45" radius="25" />
        <StraightVertex x="22" y="-10" radius="18" />
        <StraightVertex x="15" y="42" radius="10" />
        <StraightVertex x="-2" y="46" radius="10" />
        <StraightVertex x="-18" y="32" radius="12" />
        <StraightVertex x="-22" y="-10" radius="20" />
      </PointsPath>
      <Fill><SolidColor colorValue="FFFFA000" /></Fill>
      <Stroke thickness="2.5"><SolidColor colorValue="33D84315" /></Stroke>
    </Shape>
''')
    halo_markup = '''
    <!-- Radiant Golden Halo (Drawn in background behind character) -->
    <Shape name="GoldenHalo" x="210" y="150">
      <Ellipse width="320" height="240" />
      <Fill>
        <RadialGradient>
          <GradientStop position="0" colorValue="66FFD700" />
          <GradientStop position="0.6" colorValue="3300E676" />
          <GradientStop position="1" colorValue="00000000" />
        </RadialGradient>
      </Fill>
    </Shape>
'''
    lines.append(body_assembly(halo_xml=halo_markup))
    lines.append('  </Artboard>')

    lines.append('</Rive>')

    with open('scene.rml', 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print("Master RML generation completed successfully!")

if __name__ == '__main__':
    generate_all()
