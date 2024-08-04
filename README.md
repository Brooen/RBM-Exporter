# RBM-Exporter
Blender tool that converts models to Just Cause 3's RBM format

**How To Use**

To use, open a model and go to the RBM Export Panel in the Viewport. Then click "Add Scale Reference to scene" to ensure your model is lined up. Then you can delete the refrence object. Next you want to open your material and add a material model node. 
Different nodes will have different inputs. Some have none, and some have a whole ton, but the basics are the same. Each node has different sections.

*FLAGS*

This section is just a bunch of yes/no statments, like if you want something enabled or not.

*MATERIAL* (and material subsections)

This section is the material data for the model, the zones are controlled by the rgb property map and the global is for the whole model. 

*TEXTURES*

This section is where you plug in all of your textures. The tool will take the base path, then the image, then add the ddsc extension. so if the path is "textures/car" and the image file is "cardif.png", the new path will be "textures/car/cardif.ddsc". make sure not to put a / at the end of the base path. 

*BLENDER_ONLY*

This section is for stuff blender needs for the material preview to work. it will probably get bigger as I make the material previewing better.


**Currently Supported RBM Types**

-Carpaint (UV2 and UV3 support, but no deform support)
-Bavarium Shield
-Waterhull (could cause issues, last time I tested, my game crashed)
-Window
-Carlight


**How to Export**

When your model is set up with all the needed data, you need to make sure that each material is a different model, and that the model has only the nodegroup you want on it, then just click export. Then once you put all your textures in the right spot, the model should load correctly.
